from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, get_user_model
from .forms import SignUpForm
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
    
    # Leaderboard - use soloHighScore for display
    topPlayers = Profile.objects.filter(soloHighScore__gt=0).order_by('-soloHighScore')[:10]
    
    context = {
        'profile': profile,
        'matchTypes': matchTypes,
        'topPlayers': topPlayers,
    }
    return render(request, 'accounts/dashboard.html', context)


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
    return render(request, 'accounts/public_profile.html', context)