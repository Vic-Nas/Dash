from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from decimal import Decimal
from .models import MatchType, Match, MatchParticipation, SoloRun
from shop.models import Transaction
import json


@login_required
def solo(request):
    profile = request.user.profile
    context = {
        'profile': profile,
    }
    return render(request, 'matches/game.html', context)


@login_required
@require_POST
def saveSoloRun(request):
    try:
        data = json.loads(request.body)
        wallsSurvived = int(data.get('wallsSurvived', 0))
        wallsHit = int(data.get('wallsHit', 0))
        survivalTime = int(data.get('survivalTime', 0))
        finalGridState = data.get('finalGridState')
        
        # NEW SCORING: +1 coin per wall survived, -1 coin per hit
        coinsEarned = Decimal(str(wallsSurvived))
        coinsLost = Decimal(str(wallsHit))
        netCoins = coinsEarned - coinsLost
        
        with transaction.atomic():
            # Lock profile
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            balanceBefore = profile.coins
            
            # Update coins - balance can go negative but game ends at -50
            newBalance = profile.coins + netCoins
            profile.coins = newBalance
            
            # Update high score if needed
            if wallsSurvived > profile.soloHighScore:
                profile.soloHighScore = wallsSurvived
            
            profile.save(update_fields=['coins', 'soloHighScore'])
            balanceAfter = profile.coins
            
            # Create solo run record
            soloRun = SoloRun.objects.create(
                player=request.user,
                wallsSurvived=wallsSurvived,
                wallsHit=wallsHit,
                coinsEarned=coinsEarned,
                coinsLost=coinsLost,
                netCoins=netCoins,
                survivalTime=survivalTime,
                finalGridState=finalGridState,
                endedAt=timezone.now()
            )
            
            # Create transaction records
            if coinsEarned > 0:
                Transaction.objects.create(
                    user=request.user,
                    amount=coinsEarned,
                    transactionType='SOLO_REWARD',
                    description=f'Solo reward: {wallsSurvived} walls survived',
                    balanceBefore=balanceBefore,
                    balanceAfter=balanceBefore + coinsEarned
                )
            
            if coinsLost > 0:
                Transaction.objects.create(
                    user=request.user,
                    amount=-coinsLost,
                    transactionType='SOLO_PENALTY',
                    description=f'Wall hit penalties: {wallsHit} hits',
                    balanceBefore=balanceBefore + coinsEarned if coinsEarned > 0 else balanceBefore,
                    balanceAfter=balanceAfter
                )
        
        return JsonResponse({
            'success': True,
            'wallsSurvived': wallsSurvived,
            'coinsEarned': float(coinsEarned),
            'coinsLost': float(coinsLost),
            'netCoins': float(netCoins),
            'newBalance': float(balanceAfter),
            'newHighScore': wallsSurvived > (profile.soloHighScore - wallsSurvived)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def multiplayer(request):
    matchTypes = MatchType.objects.filter(isActive=True)
    
    # Add waiting player count for each match type
    for mt in matchTypes:
        waitingMatch = Match.objects.filter(
            matchType=mt,
            status='WAITING'
        ).first()
        mt.waitingCount = waitingMatch.currentPlayers if waitingMatch else 0
    
    context = {
        'matchTypes': matchTypes,
        'profile': request.user.profile,
    }
    return render(request, 'matches/multiplayer.html', context)


@login_required
@require_POST
def joinMatch(request):
    try:
        data = json.loads(request.body)
        matchTypeId = data.get('matchTypeId')
        
        if not matchTypeId:
            return JsonResponse({
                'success': False,
                'error': 'Missing matchTypeId'
            }, status=400)
        
        matchType = get_object_or_404(MatchType, id=matchTypeId, isActive=True)
        profile = request.user.profile
        
        # Check if user has enough coins
        if profile.coins < matchType.entryFee:
            return JsonResponse({
                'success': False,
                'error': f'Insufficient coins. Need {matchType.entryFee}, have {profile.coins}'
            }, status=400)
        
        with transaction.atomic():
            # Lock profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            # Find or create waiting match
            match = Match.objects.filter(
                matchType=matchType,
                status='WAITING'
            ).first()
            
            if not match:
                # Create new match
                match = Match.objects.create(
                    matchType=matchType,
                    status='WAITING',
                    gridSize=matchType.gridSize,
                    speed=matchType.speed,
                    playersRequired=matchType.playersRequired,
                    currentPlayers=0,
                    totalPot=Decimal('0')
                )
            
            # Check if already in this match
            if MatchParticipation.objects.filter(match=match, player=request.user).exists():
                return JsonResponse({
                    'success': True,
                    'matchId': match.id,
                    'currentPlayers': match.currentPlayers,
                    'playersRequired': match.playersRequired,
                    'message': 'Already in this match'
                })
            
            # Check if match is full
            if match.currentPlayers >= matchType.maxPlayers:
                return JsonResponse({
                    'success': False,
                    'error': 'Match is full'
                }, status=400)
            
            # Deduct entry fee
            balanceBefore = profile.coins
            profile.coins = F('coins') - matchType.entryFee
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            # Update match pot
            match.totalPot = F('totalPot') + matchType.entryFee
            match.currentPlayers = F('currentPlayers') + 1
            match.save(update_fields=['totalPot', 'currentPlayers'])
            match.refresh_from_db()
            
            # Create participation
            participation = MatchParticipation.objects.create(
                match=match,
                player=request.user,
                entryFeePaid=matchType.entryFee,
                livesRemaining=matchType.livesPerPlayer
            )
            
            # Create transaction
            Transaction.objects.create(
                user=request.user,
                amount=-matchType.entryFee,
                transactionType='MATCH_ENTRY',
                relatedMatch=match,
                description=f'Match entry: {matchType.name}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
            
            # Check if match should start
            shouldStart = match.currentPlayers >= match.playersRequired
            if shouldStart:
                match.status = 'STARTING'
                match.save(update_fields=['status'])
        
        return JsonResponse({
            'success': True,
            'matchId': match.id,
            'currentPlayers': match.currentPlayers,
            'playersRequired': match.playersRequired,
            'newBalance': float(balanceAfter)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@login_required
@require_POST
def forceStart(request):
    """Force start a match by paying for missing players"""
    try:
        data = json.loads(request.body)
        matchId = data.get('matchId')
        
        match = get_object_or_404(Match, id=matchId, status='WAITING')
        
        # Check if user is in this match
        participation = MatchParticipation.objects.filter(
            match=match,
            player=request.user
        ).first()
        
        if not participation:
            return JsonResponse({
                'success': False,
                'error': 'You are not in this match'
            }, status=400)
        
        # Calculate missing players
        missingPlayers = match.playersRequired - match.currentPlayers
        
        if missingPlayers <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Match already has enough players'
            }, status=400)
        
        # Calculate cost (entry fee × missing players)
        forceCost = match.matchType.entryFee * missingPlayers
        
        profile = request.user.profile
        
        if profile.coins < forceCost:
            return JsonResponse({
                'success': False,
                'error': f'Insufficient coins. Need {forceCost}, have {profile.coins}'
            }, status=400)
        
        with transaction.atomic():
            # Lock profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            # Deduct force cost
            balanceBefore = profile.coins
            profile.coins = F('coins') - forceCost
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            # Add to pot
            match.totalPot = F('totalPot') + forceCost
            match.forceStartedBy = request.user
            match.status = 'STARTING'
            match.save(update_fields=['totalPot', 'forceStartedBy', 'status'])
            match.refresh_from_db()
            
            # Create transaction
            Transaction.objects.create(
                user=request.user,
                amount=-forceCost,
                transactionType='MATCH_ENTRY',
                relatedMatch=match,
                description=f'Force start ({missingPlayers} players): {match.matchType.name}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Match force started! Paid for {missingPlayers} missing players.',
            'newBalance': float(balanceAfter)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@login_required
def lobby(request, matchId):
    match = get_object_or_404(Match, id=matchId)
    
    # Check if user is in this match
    participation = MatchParticipation.objects.filter(
        match=match,
        player=request.user
    ).first()
    
    if not participation:
        return redirect('multiplayer')
    
    # If match is IN_PROGRESS or STARTING, redirect to game
    if match.status in ['STARTING', 'IN_PROGRESS']:
        return render(request, 'matches/game_multiplayer.html', {
            'match': match,
            'participation': participation,
            'profile': request.user.profile,
        })
    
    # Otherwise show lobby
    participants = match.participants.select_related('player').all()
    
    context = {
        'match': match,
        'participation': participation,
        'participants': participants,
        'profile': request.user.profile,
    }
    return render(request, 'matches/lobby.html', context)


@login_required
@require_POST
def leaveLobby(request):
    try:
        data = json.loads(request.body)
        matchId = data.get('matchId')
        
        # Use filter().first() instead of get() to avoid exception
        match = Match.objects.filter(id=matchId).first()
        
        if not match:
            return JsonResponse({
                'success': False,
                'error': 'Match not found or already deleted'
            }, status=404)
        
        # Only allow leaving WAITING matches
        if match.status != 'WAITING':
            return JsonResponse({
                'success': False,
                'error': 'Cannot leave match that has already started'
            }, status=400)
        
        participation = MatchParticipation.objects.filter(
            match=match,
            player=request.user
        ).first()
        
        if not participation:
            return JsonResponse({
                'success': False,
                'error': 'Not in this match'
            }, status=400)
        
        with transaction.atomic():
            # Lock profile
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            # Refund entry fee
            balanceBefore = profile.coins
            profile.coins = F('coins') + participation.entryFeePaid
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            # Update match
            match.totalPot = F('totalPot') - participation.entryFeePaid
            match.currentPlayers = F('currentPlayers') - 1
            match.save(update_fields=['totalPot', 'currentPlayers'])
            match.refresh_from_db()
            
            # Create refund transaction
            Transaction.objects.create(
                user=request.user,
                amount=participation.entryFeePaid,
                transactionType='REFUND',
                relatedMatch=match,
                description=f'Left lobby: {match.matchType.name}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
            
            # Delete participation
            participation.delete()
            
            # If match is now empty, delete it
            if match.currentPlayers == 0:
                match.delete()
        
        return JsonResponse({
            'success': True,
            'newBalance': float(balanceAfter),
            'message': 'Left lobby and refunded'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False, 
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)