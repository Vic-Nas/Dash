from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import F
from decimal import Decimal
from .models import CoinPackage, CoinPurchase, Transaction
from cosmetics.models import BotSkin, OwnedSkin
import json
import os


@login_required
def shop(request):
    packages = CoinPackage.objects.filter(isActive=True)
    skins = BotSkin.objects.all()
    ownedSkins = request.user.ownedSkins.values_list('skin_id', flat=True)
    
    context = {
        'packages': packages,
        'skins': skins,
        'ownedSkins': list(ownedSkins),
        'profile': request.user.profile,
    }
    return render(request, 'shop/shop.html', context)


@login_required
@require_POST
def buySkin(request):
    try:
        data = json.loads(request.body)
        skinId = data.get('skinId')
        
        skin = get_object_or_404(BotSkin, id=skinId)
        
        # Check if already owned
        if OwnedSkin.objects.filter(player=request.user, skin=skin).exists():
            return JsonResponse({'success': False, 'error': 'Skin already owned'})
        
        # Check if default (free)
        if skin.isDefault:
            OwnedSkin.objects.create(player=request.user, skin=skin)
            return JsonResponse({'success': True, 'message': 'Free skin claimed!'})
        
        profile = request.user.profile
        
        # Check balance
        if profile.coins < skin.price:
            return JsonResponse({'success': False, 'error': 'Insufficient coins'})
        
        # Atomic transaction
        with transaction.atomic():
            # Lock profile row
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            balanceBefore = profile.coins
            profile.coins = F('coins') - skin.price
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            # Create ownership
            OwnedSkin.objects.create(player=request.user, skin=skin)
            
            # Create transaction record
            Transaction.objects.create(
                user=request.user,
                amount=-skin.price,
                transactionType='SKIN_PURCHASE',
                relatedSkin=skin,
                description=f'Purchased skin: {skin.name}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
        
        return JsonResponse({
            'success': True,
            'newBalance': float(balanceAfter),
            'message': f'Purchased {skin.name}!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def equipSkin(request):
    try:
        data = json.loads(request.body)
        skinId = data.get('skinId')
        
        skin = get_object_or_404(BotSkin, id=skinId)
        
        # Check ownership
        if not OwnedSkin.objects.filter(player=request.user, skin=skin).exists():
            return JsonResponse({'success': False, 'error': 'Skin not owned'})
        
        profile = request.user.profile
        profile.currentSkin = skin
        profile.save(update_fields=['currentSkin'])
        
        return JsonResponse({
            'success': True,
            'message': f'Equipped {skin.name}!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def createPaymentIntent(request):
    try:
        data = json.loads(request.body)
        packageId = data.get('packageId')
        
        package = get_object_or_404(CoinPackage, id=packageId, isActive=True)
        
        # Note: Stripe integration would go here
        # For now, return error indicating Stripe not configured
        stripeSecretKey = os.environ.get('STRIPE_SECRET_KEY')
        
        if not stripeSecretKey:
            return JsonResponse({
                'success': False,
                'error': 'Payment system not configured. Please contact support.'
            })
        
        # In production, create Stripe payment intent:
        import stripe
        stripe.api_key = stripeSecretKey
        intent = stripe.PaymentIntent.create(
            amount=int(package.price * 100),
            currency='usd',
            metadata={'packageId': package.id, 'userId': request.user.id}
        )
        
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
            'clientSecret': intent.client_secret
        })
        

        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def stripeWebhook(request):
    try:
        # Note: Stripe webhook handling would go here
        # This endpoint should verify the webhook signature and process events
        
        # import stripe
        # stripeWebhookSecret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        # payload = request.body
        # sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        # 
        # event = stripe.Webhook.construct_event(
        #     payload, sig_header, stripeWebhookSecret
        # )
        # 
        # if event.type == 'payment_intent.succeeded':
        #     paymentIntent = event.data.object
        #     paymentIntentId = paymentIntent.id
        #     
        #     with transaction.atomic():
        #         purchase = CoinPurchase.objects.select_for_update().get(
        #             stripePaymentIntentId=paymentIntentId
        #         )
        #         
        #         if purchase.status != 'COMPLETED':
        #             purchase.status = 'COMPLETED'
        #             purchase.completedAt = timezone.now()
        #             purchase.save()
        #             
        #             profile = purchase.user.profile
        #             profile = type(profile).objects.select_for_update().get(pk=profile.pk)
        #             
        #             balanceBefore = profile.coins
        #             profile.coins = F('coins') + purchase.coinAmount
        #             profile.save(update_fields=['coins'])
        #             profile.refresh_from_db()
        #             balanceAfter = profile.coins
        #             
        #             Transaction.objects.create(
        #                 user=purchase.user,
        #                 amount=purchase.coinAmount,
        #                 transactionType='PURCHASE',
        #                 description=f'Purchased {purchase.package.name}',
        #                 balanceBefore=balanceBefore,
        #                 balanceAfter=balanceAfter
        #             )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)