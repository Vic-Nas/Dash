from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from decimal import Decimal
from .models import CoinPackage, CoinPurchase, Transaction
import json
import os


@login_required
def shop(request):
    packages = CoinPackage.objects.filter(isActive=True)
    
    context = {
        'packages': packages,
        'profile': request.user.profile,
        'stripePublicKey': os.environ.get('STRIPE_PUBLIC_KEY', ''),
    }
    return render(request, 'shop/shop.html', context)


@login_required
@require_POST
def createPaymentIntent(request):
    try:
        data = json.loads(request.body)
        packageId = data.get('packageId')
        
        package = get_object_or_404(CoinPackage, id=packageId, isActive=True)
        
        # Check if Stripe is configured
        stripeSecretKey = os.environ.get('STRIPE_SECRET_KEY')
        if not stripeSecretKey:
            return JsonResponse({
                'success': False,
                'error': 'Payment system not configured. STRIPE_SECRET_KEY is missing.'
            }, status=500)
        
        # Check if test mode is enabled
        testMode = os.environ.get('STRIPE_TEST_MODE', 'false').lower() == 'true'
        
        # Create Stripe payment intent
        import stripe
        stripe.api_key = stripeSecretKey
        
        # In test mode, allow test card numbers
        createParams = {
            'amount': int(package.price * 100),  # Convert to cents
            'currency': 'usd',
            'metadata': {
                'packageId': package.id,
                'userId': request.user.id
            }
        }
        
        # Enable test mode if configured
        if testMode:
            createParams['payment_method_types'] = ['card']
        
        intent = stripe.PaymentIntent.create(**createParams)
        
        # Create purchase record
        CoinPurchase.objects.create(
            user=request.user,
            package=package,
            stripePaymentIntentId=intent.id,
            status='PENDING',
            coinAmount=package.coins,
            pricePaid=package.price
        )
        
        return JsonResponse({
            'success': True,
            'clientSecret': intent.client_secret,
            'testMode': testMode
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@csrf_exempt
@require_POST
def stripeWebhook(request):
    """Handle Stripe webhook events"""
    try:
        import stripe
        
        payload = request.body
        sigHeader = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        stripeWebhookSecret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        if not stripeWebhookSecret:
            return JsonResponse({'error': 'Webhook secret not configured'}, status=500)
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sigHeader, stripeWebhookSecret
            )
        except ValueError:
            return JsonResponse({'error': 'Invalid payload'}, status=400)
        except stripe.error.SignatureVerificationError:
            return JsonResponse({'error': 'Invalid signature'}, status=400)
        
        # Handle payment_intent.succeeded event
        if event['type'] == 'payment_intent.succeeded':
            paymentIntent = event['data']['object']
            paymentIntentId = paymentIntent['id']
            
            with transaction.atomic():
                try:
                    purchase = CoinPurchase.objects.select_for_update().get(
                        stripePaymentIntentId=paymentIntentId
                    )
                    
                    # Only process if not already completed
                    if purchase.status != 'COMPLETED':
                        purchase.status = 'COMPLETED'
                        purchase.completedAt = timezone.now()
                        purchase.save()
                        
                        # Add coins to user's balance
                        profile = purchase.user.profile
                        profile = type(profile).objects.select_for_update().get(pk=profile.pk)
                        
                        balanceBefore = profile.coins
                        profile.coins = F('coins') + purchase.coinAmount
                        profile.save(update_fields=['coins'])
                        profile.refresh_from_db()
                        balanceAfter = profile.coins
                        
                        # Create transaction record
                        Transaction.objects.create(
                            user=purchase.user,
                            amount=purchase.coinAmount,
                            transactionType='PURCHASE',
                            description=f'Purchased {purchase.package.name}',
                            balanceBefore=balanceBefore,
                            balanceAfter=balanceAfter
                        )
                        
                except CoinPurchase.DoesNotExist:
                    return JsonResponse({'error': 'Purchase not found'}, status=404)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=400)