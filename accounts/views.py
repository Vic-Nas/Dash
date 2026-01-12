from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, get_user_model, logout, update_session_auth_hash
from django.http import JsonResponse
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import ProfilePictureForm
from matches.models import MatchType
from accounts.models import Profile
from chat.models import DirectMessage
from shop.models import SystemSettings, Transaction
from decimal import Decimal
import random
import string


def generateRandomUsername():
    """Generate a random username like 'player_abc123'"""
    User = get_user_model()
    while True:
        randomPart = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        username = f'player_{randomPart}'
        if not User.objects.filter(username=username).exists():
            return username


def generateRandomPassword():
    """Generate a random password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))



from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST' and 'username' in request.POST:
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
        else:
            error = 'Invalid username or password.'
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form, 'error': error})

from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def guestLogin(request):
    if request.method == 'POST':
        User = get_user_model()
        username = generateRandomUsername()
        password = generateRandomPassword()
        user = User.objects.create_user(username=username, password=password)
        profile = user.profile
        profile.hasChangedPassword = False
        profile.save()
        request.session['temp_password'] = password
        login(request, user)
        return redirect('dashboard')
    return redirect('login')


@login_required
def dashboard(request):
    profile = request.user.profile
    matchTypes = MatchType.objects.filter(isActive=True)
    
    # Update last activity
    profile.lastActivityAt = timezone.now()
    profile.save(update_fields=['lastActivityAt'])
    
    # Leaderboard - sort by solo high score, refresh from database
    topPlayers = Profile.objects.filter(soloHighScore__gt=0).select_related('user').order_by('-soloHighScore')[:10]
    
    # Get unread message count
    unreadCount = DirectMessage.objects.filter(
        recipient=request.user,
        isRead=False
    ).count()
    
    # Get temporary password if it exists (first login)
    tempPassword = request.session.pop('temp_password', None)
    
    # Check if account will be deleted on logout
    willDeleteOnLogout = not profile.hasChangedPassword
    
    context = {
        'profile': profile,
        'matchTypes': matchTypes,
        'topPlayers': topPlayers,
        'unreadCount': unreadCount,
        'tempPassword': tempPassword,
        'willDeleteOnLogout': willDeleteOnLogout,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def customLogout(request):
    """Custom logout view that deletes anonymous accounts that haven't changed password"""
    profile = request.user.profile
    user = request.user
    
    # Delete account if user never changed password
    if not profile.hasChangedPassword:
        logout(request)
        user.delete()  # This also deletes the profile due to CASCADE
        return redirect('/login/')
    
    logout(request)
    return redirect('/login/')


@login_required
def uploadProfilePicture(request):
    """Handle profile picture upload"""
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ProfilePictureForm(instance=request.user.profile)
    
    context = {
        'form': form,
        'profile': request.user.profile,
    }
    return render(request, 'accounts/uploadProfilePic.html', context)


@login_required
def publicProfile(request, username):
    User = get_user_model()
    try:
        profileUser = User.objects.get(username=username)
        profileData = profileUser.profile
        isOwnProfile = profileUser == request.user
        context = {
            'profileUser': profileUser,
            'profileData': profileData,
            'isOwnProfile': isOwnProfile,
            'currentUserProfile': request.user.profile,
        }
        # Convert all context keys to camelCase for template
        context = {
            'profileUser': profileUser,
            'profileData': profileData,
            'isOwnProfile': isOwnProfile,
            'currentUserProfile': request.user.profile,
        }
        return render(request, 'accounts/publicProfile.html', context)
    except User.DoesNotExist:
        return render(request, 'accounts/userNotFound.html', {'username': username}, status=404)


@login_required
def profileSearch(request):
    """Search for a user by username and redirect to profile"""
    username = request.GET.get('username', '').strip()
    if username:
        return redirect('publicProfile', username=username)
    return redirect('dashboard')


@login_required
def accountSettings(request):
    """Account settings page for password and username changes"""
    profile = request.user.profile
    usernameChangeCost = SystemSettings.getInt('username_change_cost', 100)
    
    context = {
        'profile': profile,
        'usernameChangeCost': usernameChangeCost,
    }
    return render(request, 'accounts/settings.html', context)


@login_required
@require_POST
def changePassword(request):
    """Change password - always free"""
    try:
        newPassword = request.POST.get('newPassword')
        confirmPassword = request.POST.get('confirmPassword')
        
        if not newPassword or len(newPassword) < 8:
            return JsonResponse({
                'success': False,
                'error': 'Password must be at least 8 characters'
            }, status=400)
        
        if newPassword != confirmPassword:
            return JsonResponse({
                'success': False,
                'error': 'Passwords do not match'
            }, status=400)
        
        user = request.user
        user.set_password(newPassword)
        user.save()
        update_session_auth_hash(request, user)  # Keep the user logged in after password change
        
        # Mark that user has changed password
        profile = user.profile
        profile.hasChangedPassword = True
        profile.save(update_fields=['hasChangedPassword'])
        
        return JsonResponse({
            'success': True,
            'message': 'Password changed successfully! Your account is now secured.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def changeUsername(request):
    """Change username - costs coins (configurable in admin)"""
    try:
        newUsername = request.POST.get('newUsername', '').strip()
        
        if not newUsername:
            return JsonResponse({
                'success': False,
                'error': 'Username cannot be empty'
            }, status=400)
        
        if len(newUsername) < 3 or len(newUsername) > 20:
            return JsonResponse({
                'success': False,
                'error': 'Username must be 3-20 characters'
            }, status=400)
        
        # Check if username is taken
        User = get_user_model()
        if User.objects.filter(username=newUsername).exists():
            return JsonResponse({
                'success': False,
                'error': 'Username already taken'
            }, status=400)
        
        # Get username change cost from settings
        usernameChangeCost = Decimal(str(SystemSettings.getInt('username_change_cost', 100)))
        
        with transaction.atomic():
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            # Check if user has enough coins
            if profile.coins < usernameChangeCost:
                return JsonResponse({
                    'success': False,
                    'error': f'Insufficient coins. Need {usernameChangeCost}, have {profile.coins}'
                }, status=400)
            
            # Deduct coins
            balanceBefore = profile.coins
            profile.coins = F('coins') - usernameChangeCost
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            # Change username
            user = request.user
            oldUsername = user.username
            user.username = newUsername
            user.save(update_fields=['username'])
            
            # Create transaction record
            Transaction.objects.create(
                user=user,
                amount=-usernameChangeCost,
                transactionType='USERNAME_CHANGE',
                description=f'Changed username from {oldUsername} to {newUsername}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Username changed to {newUsername}!',
            'newBalance': float(balanceAfter)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)