from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, get_user_model, logout
from django.http import JsonResponse
from .forms import SignUpForm, ProfilePictureForm
from matches.models import MatchType
from accounts.models import Profile


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def dashboard(request):
    profile = request.user.profile
    matchTypes = MatchType.objects.filter(isActive=True)
    
    # Leaderboard - sort by solo high score
    topPlayers = Profile.objects.filter(soloHighScore__gt=0).order_by('-soloHighScore')[:10]
    
    context = {
        'profile': profile,
        'matchTypes': matchTypes,
        'topPlayers': topPlayers,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def customLogout(request):
    """Custom logout view that accepts GET requests"""
    logout(request)
    return redirect('login')


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
    profileUser = get_object_or_404(User, username=username)
    profileData = profileUser.profile
    
    # Check if viewing own profile
    isOwnProfile = profileUser == request.user
    
    context = {
        'profileUser': profileUser,
        'profileData': profileData,
        'isOwnProfile': isOwnProfile,
        'currentUserProfile': request.user.profile,
    }
    return render(request, 'accounts/publicProfile.html', context)


@login_required
def profileSearch(request):
    """Search for a user by username and redirect to profile"""
    username = request.GET.get('username', '').strip()
    if username:
        return redirect('publicProfile', username=username)
    return redirect('dashboard')