from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.core.paginator import Paginator
from decimal import Decimal
from .models import MatchType, Match, MatchParticipation, SoloRun, ProgressiveRun
from shop.models import Transaction, SystemSettings
import json
import random


# Bot names for realistic appearance
BOT_NAMES = [
    'Alex_92', 'Shadow', 'NoobMaster', 'ProGamer_88', 'Viper', 'Phoenix',
    'Storm', 'Blaze', 'Echo', 'Nexus', 'Titan', 'Specter', 'Razor',
    'Cyber_', 'Void', 'Nova', 'Apex', 'Hunter'
]


def createBotParticipant(match, matchType):
    """Create a bot participant for the match"""
    botName = random.choice(BOT_NAMES)
    MatchParticipation.objects.create(
        match=match,
        player=None,
        username=botName,
        entryFeePaid=matchType.entryFee,
        isBot=True
    )


def enforceReplayLimit():
    """Delete oldest replays if count exceeds maxReplaysStored setting."""
    maxReplays = SystemSettings.getInt('maxReplaysStored', 50)
    
    # Count total replays (both SoloRun and ProgressiveRun have replayData)
    soloWithReplay = SoloRun.objects.filter(replayData__isnull=False).count()
    progressiveWithReplay = ProgressiveRun.objects.filter(replayData__isnull=False).count()
    totalReplays = soloWithReplay + progressiveWithReplay
    
    if totalReplays > maxReplays:
        # Delete oldest solo replays first
        replayToDelete = totalReplays - maxReplays
        
        oldestSolo = SoloRun.objects.filter(replayData__isnull=False).order_by('endedAt')[:replayToDelete]
        deleteCount = oldestSolo.count()
        
        if deleteCount > 0:
            oldestSolo.delete()
            replayToDelete -= deleteCount
        
        # If we still need to delete more, delete from progressive
        if replayToDelete > 0:
            oldestProgressive = ProgressiveRun.objects.filter(replayData__isnull=False).order_by('endedAt')[:replayToDelete]
            oldestProgressive.delete()


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
        replayData = data.get('replayData')
        
        coinsEarned = Decimal(str(wallsSurvived))
        coinsLost = Decimal(str(wallsHit))
        netCoins = coinsEarned - coinsLost
        
        with transaction.atomic():
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            balanceBefore = profile.coins
            
            newBalance = profile.coins + netCoins
            profile.coins = newBalance
            
            if wallsSurvived > profile.soloHighScore:
                profile.soloHighScore = wallsSurvived
            
            profile.save(update_fields=['coins', 'soloHighScore'])
            balanceAfter = profile.coins
            
            soloRun = SoloRun.objects.create(
                player=request.user,
                wallsSurvived=wallsSurvived,
                wallsHit=wallsHit,
                coinsEarned=coinsEarned,
                coinsLost=coinsLost,
                netCoins=netCoins,
                survivalTime=survivalTime,
                finalGridState=finalGridState,
                replayData=replayData,
                isPublic=True,
                endedAt=timezone.now()
            )
            
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
        
        # Enforce replay storage limit (outside transaction)
        enforceReplayLimit()
        
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
def progressive(request):
    profile = request.user.profile
    
    maxLevel = SystemSettings.getInt('progressiveMaxLevel', 30)
    costPerAttempt = SystemSettings.getInt('progressiveCostPerAttempt', 10)
    
    context = {
        'profile': profile,
        'maxLevel': maxLevel,
        'costPerAttempt': costPerAttempt,
    }
    return render(request, 'matches/gameProgressive.html', context)


@login_required
@require_POST
def saveProgressiveRun(request):
    try:
        data = json.loads(request.body)
        level = int(data.get('level', 1))
        botsEliminated = int(data.get('botsEliminated', 0))
        won = bool(data.get('won', False))
        survivalTime = int(data.get('survivalTime', 0))
        finalGridState = data.get('finalGridState')
        replayData = data.get('replayData')
        
        costPerAttempt = Decimal(str(SystemSettings.getInt('progressiveCostPerAttempt', 10)))
        
        with transaction.atomic():
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            balanceBefore = profile.coins
            
            # Deduct entry cost
            profile.coins = F('coins') - costPerAttempt
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfterEntry = profile.coins
            
            # Create entry transaction
            Transaction.objects.create(
                user=request.user,
                amount=-costPerAttempt,
                transactionType='PROGRESSIVE_ENTRY',
                description=f'Progressive level {level} attempt',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfterEntry
            )
            
            coinsEarned = Decimal('0')
            if won:
                coinsEarned = Decimal(str(level * 10))
                profile.coins = F('coins') + coinsEarned
                
                if level > profile.progressiveHighestLevel:
                    profile.progressiveHighestLevel = level
                
                profile.save(update_fields=['coins', 'progressiveHighestLevel'])
                profile.refresh_from_db()
                balanceAfter = profile.coins
                
                # Create reward transaction
                Transaction.objects.create(
                    user=request.user,
                    amount=coinsEarned,
                    transactionType='PROGRESSIVE_REWARD',
                    description=f'Progressive level {level} victory',
                    balanceBefore=balanceAfterEntry,
                    balanceAfter=balanceAfter
                )
            else:
                balanceAfter = balanceAfterEntry
            
            ProgressiveRun.objects.create(
                player=request.user,
                level=level,
                botsEliminated=botsEliminated,
                won=won,
                survivalTime=survivalTime,
                coinsSpent=costPerAttempt,
                coinsEarned=coinsEarned,
                finalGridState=finalGridState,
                replayData=replayData,
                isPublic=True,
                endedAt=timezone.now()
            )
        
        # Enforce replay storage limit (outside transaction)
        enforceReplayLimit()
        
        return JsonResponse({
            'success': True,
            'won': won,
            'level': level,
            'botsEliminated': botsEliminated,
            'coinsEarned': float(coinsEarned),
            'newBalance': float(balanceAfter),
            'newHighestLevel': level > profile.progressiveHighestLevel
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def matchmaking(request):
    matchTypes = MatchType.objects.filter(isActive=True)
    
    for mt in matchTypes:
        waitingMatch = Match.objects.filter(
            matchType=mt,
            status='WAITING'
        ).first()
        
        # If no waiting match and this match type has bots, create one with a bot
        if not waitingMatch and mt.hasBot:
            waitingMatch = Match.objects.create(
                matchType=mt,
                status='WAITING',
                gridSize=mt.gridSize,
                speed=mt.speed,
                playersRequired=mt.playersRequired,
                currentPlayers=1,
                totalPot=Decimal('0')
            )
            # Add bot to the new match
            createBotParticipant(waitingMatch, mt)
            waitingMatch.currentPlayers = 1
            waitingMatch.save(update_fields=['currentPlayers'])
        
        mt.waitingCount = waitingMatch.currentPlayers if waitingMatch else 0
        mt.hasWaitingPlayers = mt.waitingCount > 0
    
    hasAnyWaitingPlayers = any(mt.hasWaitingPlayers for mt in matchTypes)
    
    context = {
        'matchTypes': matchTypes,
        'profile': request.user.profile,
        'hasAnyWaitingPlayers': hasAnyWaitingPlayers,
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
        
        if profile.coins < matchType.entryFee:
            return JsonResponse({
                'success': False,
                'error': f'Insufficient coins. Need {matchType.entryFee}, have {profile.coins}'
            }, status=400)
        
        with transaction.atomic():
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            match = Match.objects.filter(
                matchType=matchType,
                status='WAITING'
            ).first()
            
            isNewMatch = False
            if not match:
                match = Match.objects.create(
                    matchType=matchType,
                    status='WAITING',
                    gridSize=matchType.gridSize,
                    speed=matchType.speed,
                    playersRequired=matchType.playersRequired,
                    currentPlayers=0,
                    totalPot=Decimal('0')
                )
                isNewMatch = True
                
                # Add bot if matchType has bots enabled
                if matchType.hasBot:
                    createBotParticipant(match, matchType)
                    match.currentPlayers += 1
                    match.save(update_fields=['currentPlayers'])
            
            if MatchParticipation.objects.filter(match=match, player=request.user).exists():
                return JsonResponse({
                    'success': True,
                    'matchId': match.id,
                    'currentPlayers': match.currentPlayers,
                    'playersRequired': match.playersRequired,
                    'message': 'Already in this match'
                })
            
            if match.currentPlayers >= matchType.maxPlayers:
                return JsonResponse({
                    'success': False,
                    'error': 'Match is full'
                }, status=400)
            
            balanceBefore = profile.coins
            profile.coins = F('coins') - matchType.entryFee
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            match.totalPot += matchType.entryFee
            match.currentPlayers += 1
            match.save(update_fields=['totalPot', 'currentPlayers'])
            
            participation = MatchParticipation.objects.create(
                match=match,
                player=request.user,
                entryFeePaid=matchType.entryFee
            )
            
            # Remove bot if 2+ real players have joined
            realPlayerCount = MatchParticipation.objects.filter(match=match, isBot=False).count()
            if realPlayerCount >= 2:
                bot = MatchParticipation.objects.filter(match=match, isBot=True).first()
                if bot:
                    # Remove bot from the GameEngine if it's loaded
                    from matches.consumers import ACTIVE_GAMES
                    if match.id in ACTIVE_GAMES:
                        engine = ACTIVE_GAMES[match.id]
                        engine.removePlayer(f"bot_{bot.id}")
                    
                    bot.delete()
                    match.currentPlayers = match.currentPlayers - 1 if match.currentPlayers else 0
                    match.save(update_fields=['currentPlayers'])
            Transaction.objects.create(
                user=request.user,
                amount=-matchType.entryFee,
                transactionType='MATCH_ENTRY',
                relatedMatch=match,
                description=f'Match entry: {matchType.name}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
            
            shouldAutoStart = match.currentPlayers >= matchType.maxPlayers
            if shouldAutoStart:
                match.status = 'STARTING'
                match.save(update_fields=['status'])
        
        return JsonResponse({
            'success': True,
            'matchId': match.id,
            'currentPlayers': match.currentPlayers,
            'playersRequired': match.playersRequired,
            'maxPlayers': matchType.maxPlayers,
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
    try:
        data = json.loads(request.body)
        matchId = data.get('matchId')
        
        match = get_object_or_404(Match, id=matchId, status='WAITING')
        
        participation = MatchParticipation.objects.filter(
            match=match,
            player=request.user
        ).first()
        
        if not participation:
            return JsonResponse({
                'success': False,
                'error': 'You are not in this match'
            }, status=400)
        
        if match.currentPlayers < match.playersRequired:
            return JsonResponse({
                'success': False,
                'error': f'Need at least {match.playersRequired} players to start. Currently have {match.currentPlayers}.'
            }, status=400)
        
        missingPlayers = match.matchType.maxPlayers - match.currentPlayers
        
        if missingPlayers <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Match is already full'
            }, status=400)
        
        forceCost = match.matchType.entryFee * missingPlayers
        
        profile = request.user.profile
        
        if profile.coins < forceCost:
            return JsonResponse({
                'success': False,
                'error': f'Insufficient coins. Need {forceCost}, have {profile.coins}'
            }, status=400)
        
        with transaction.atomic():
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            balanceBefore = profile.coins
            profile.coins = F('coins') - forceCost
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            match.totalPot = F('totalPot') + forceCost
            match.forceStartedBy = request.user
            match.status = 'STARTING'
            match.save(update_fields=['totalPot', 'forceStartedBy', 'status'])
            match.refresh_from_db()
            
            Transaction.objects.create(
                user=request.user,
                amount=-forceCost,
                transactionType='MATCH_ENTRY',
                relatedMatch=match,
                description=f'Force start ({missingPlayers} slots): {match.matchType.name}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Match force started! Paid for {missingPlayers} empty slots.',
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
    
    participation = MatchParticipation.objects.filter(
        match=match,
        player=request.user
    ).first()
    
    if not participation:
        return redirect('matches:matchmaking')
    
    if match.status in ['STARTING', 'IN_PROGRESS']:
        return render(request, 'matches/gameMultiplayer.html', {
            'match': match,
            'participation': participation,
            'profile': request.user.profile,
        })
    
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
        
        match = Match.objects.filter(id=matchId).first()
        
        if not match:
            return JsonResponse({
                'success': False,
                'error': 'Match not found or already deleted'
            }, status=404)
        
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
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            balanceBefore = profile.coins
            profile.coins = F('coins') + participation.entryFeePaid
            profile.save(update_fields=['coins'])
            profile.refresh_from_db()
            balanceAfter = profile.coins
            
            match.totalPot = F('totalPot') - participation.entryFeePaid
            match.currentPlayers = F('currentPlayers') - 1
            match.save(update_fields=['totalPot', 'currentPlayers'])
            match.refresh_from_db()
            
            Transaction.objects.create(
                user=request.user,
                amount=participation.entryFeePaid,
                transactionType='REFUND',
                relatedMatch=match,
                description=f'Left lobby: {match.matchType.name}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
            
            participation.delete()
            
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


@login_required
@require_POST
def checkAutoStart(request):
    try:
        data = json.loads(request.body)
        matchId = data.get('matchId')
        
        match = get_object_or_404(Match, id=matchId, status='WAITING')
        
        # Only auto-start if we have enough real players (bots don't count for auto-start)
        realPlayerCount = MatchParticipation.objects.filter(match=match, isBot=False).count()
        if realPlayerCount >= match.playersRequired:
            match.status = 'STARTING'
            match.save(update_fields=['status'])
            return JsonResponse({'success': True, 'started': True})
        
        return JsonResponse({'success': True, 'started': False})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

        
@login_required
def checkActivity(request):
    hasActivity = Match.objects.filter(
        status='WAITING',
        currentPlayers__gt=0
    ).exists()
    
    return JsonResponse({'hasActivity': hasActivity})


# ============================================
# NEW REPLAY BROWSER VIEWS
# ============================================

@login_required
def browseReplays(request):
    """Browse public replays with filtering and pagination"""
    mode = request.GET.get('mode', 'all')
    showLosses = request.GET.get('losses', 'all')  # 'all', 'wins', 'losses'
    page = request.GET.get('page', 1)
    
    replays = []
    
    user_id = request.user.id if request.user.is_authenticated else None

    # Only show replays where the user is the player/owner
    # Solo replays
    if mode in ['all', 'solo']:
        solo_runs = SoloRun.objects.filter(
            player_id=user_id,
            replayData__isnull=False
        ).select_related('player').order_by('-wallsSurvived', '-endedAt')[:50]
        for run in solo_runs:
            replays.append({
                'type': 'solo',
                'id': run.id,
                'player': run.player.username,
                'player_id': run.player.id,
                'score': run.wallsSurvived,
                'score_label': f'{run.wallsSurvived} walls',
                'date': run.endedAt,
                'time': run.survivalTime,
            })

    # Progressive replays (all runs, unless filtered)
    if mode in ['all', 'progressive']:
        filters = {
            'player_id': user_id,
            'replayData__isnull': False
        }
        
        if showLosses == 'wins':
            filters['won'] = True
        elif showLosses == 'losses':
            filters['won'] = False
        
        progressive_runs = ProgressiveRun.objects.filter(
            **filters
        ).select_related('player').order_by('-level', '-endedAt')[:50]
        for run in progressive_runs:
            replays.append({
                'type': 'progressive',
                'id': run.id,
                'player': run.player.username,
                'player_id': run.player.id,
                'score': run.level,
                'score_label': f'Level {run.level}',
                'date': run.endedAt,
                'time': run.survivalTime,
                'won': run.won,
            })

    # Multiplayer replays (all participants with replay data)
    if mode in ['all', 'multiplayer']:
        match_participations = MatchParticipation.objects.filter(
            player_id=user_id,
            replayData__isnull=False
        ).select_related('player', 'match', 'match__matchType').order_by('-match__completedAt')[:50]
        for participation in match_participations:
            replays.append({
                'type': 'multiplayer',
                'id': participation.id,
                'player': participation.player.username,
                'player_id': participation.player.id,
                'score': int(participation.coinReward) if participation.coinReward else 0,
                'score_label': f'{int(participation.coinReward) if participation.coinReward else 0} coins won',
                'date': participation.match.completedAt,
                'time': participation.survivalTime or 0,
                'match_type': participation.match.matchType.name,
                'placement': participation.placement,
            })
    
    # Sort by date (most recent first)
    replays.sort(key=lambda x: x['date'], reverse=True)
    
    # Pagination
    paginator = Paginator(replays, 20)
    page_obj = paginator.get_page(page)
    
    context = {
        'replays': page_obj,
        'mode': mode,
        'losses': showLosses,
        'profile': request.user.profile,
        'own_replay_cost': SystemSettings.getInt('replayViewCostOwn', 0),
        'other_replay_cost': SystemSettings.getInt('replayViewCostOther', 50),
    }
    
    return render(request, 'matches/browseReplays.html', context)


@login_required
@require_POST
def watchReplay(request):
    """Deduct coins and redirect to replay viewer"""
    try:
        data = json.loads(request.body)
        replayType = data.get('type')
        replayId = data.get('id')
        
        if not replayType or not replayId:
            return JsonResponse({
                'success': False,
                'error': 'Missing type or id'
            }, status=400)
        
        # Get replay and check ownership
        ownerId = None
        replayExists = False
        
        if replayType == 'solo':
            run = SoloRun.objects.filter(id=replayId, replayData__isnull=False).first()
            if run:
                ownerId = run.player.id
                replayExists = True
        elif replayType == 'progressive':
            run = ProgressiveRun.objects.filter(id=replayId, replayData__isnull=False).first()
            if run:
                ownerId = run.player.id
                replayExists = True
        elif replayType == 'multiplayer':
            participation = MatchParticipation.objects.filter(id=replayId, replayData__isnull=False).first()
            if participation:
                ownerId = participation.player.id
                replayExists = True
        
        if not replayExists:
            return JsonResponse({'success': False, 'error': 'Replay not found'}, status=404)
        
        # Get cost based on ownership
        isOwner = ownerId == request.user.id
        if isOwner:
            replayCost = SystemSettings.getInt('replayViewCostOwn', 0)
        else:
            replayCost = SystemSettings.getInt('replayViewCostOther', 50)

        # Check if already paid
        from .models import ReplayView
        alreadyPaid = ReplayView.objects.filter(user=request.user.profile, replay_type=replayType, replay_id=replayId, paid=True).exists()
        if alreadyPaid:
            return JsonResponse({
                'success': True,
                'paid': False,
                'message': 'Already paid'
            })

        # Deduct coins and record payment
        with transaction.atomic():
            profile = request.user.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            balanceBefore = profile.coins
            if profile.coins < replayCost:
                return JsonResponse({'success': False, 'error': 'Insufficient coins'}, status=402)
            profile.coins -= replayCost
            profile.save(update_fields=['coins'])
            balanceAfter = profile.coins
            Transaction.objects.create(
                user=request.user,
                amount=-replayCost,
                transactionType='REPLAY_VIEW',
                description=f'Paid to view {replayType} replay #{replayId}',
                balanceBefore=balanceBefore,
                balanceAfter=balanceAfter
            )
            ReplayView.objects.create(
                user=profile,
                replay_type=replayType,
                replay_id=replayId,
                paid=True
            )
        return JsonResponse({
            'success': True,
            'paid': True,
            'cost': replayCost,
            'newBalance': float(balanceAfter)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def replayViewer(request, replayType, replayId):
    """Render replay viewer page"""
    replayData = None
    metadata = {}
    playerId = None
    
    if replayType == 'solo':
        run = get_object_or_404(SoloRun, id=replayId, replayData__isnull=False)
        replayData = run.replayData
        playerId = run.player.id
        metadata = {
            'type': 'Solo Mode',
            'player': run.player.username,
            'score': f'{run.wallsSurvived} walls survived',
            'time': f'{run.survivalTime}s',
            'date': run.endedAt,
        }
    elif replayType == 'progressive':
        run = get_object_or_404(ProgressiveRun, id=replayId, replayData__isnull=False)
        replayData = run.replayData
        playerId = run.player.id
        metadata = {
            'type': 'Progressive Mode',
            'player': run.player.username,
            'score': f'Level {run.level}' + (' (Victory)' if run.won else ' (Defeated)'),
            'time': f'{run.survivalTime}s',
            'date': run.endedAt,
        }
    elif replayType == 'multiplayer':
        participation = get_object_or_404(MatchParticipation, id=replayId, replayData__isnull=False)
        replayData = participation.replayData
        playerId = participation.player.id
        metadata = {
            'type': 'Multiplayer',
            'player': participation.player.username,
            'score': f'{int(participation.coinReward)} coins won',
            'time': f'{participation.survivalTime or 0}s',
            'date': participation.match.completedAt,
            'match_type': participation.match.matchType.name,
        }
    else:
        return redirect('matches:browseReplays')
    
    # Check if user needs to pay for this replay
    from .models import ReplayView
    profile = request.user.profile
    isOwner = request.user.id == playerId
    hasPaid = ReplayView.objects.filter(user=profile, replay_type=replayType, replay_id=replayId, paid=True).exists()
    
    # Get appropriate cost based on ownership
    if isOwner:
        replayCost = SystemSettings.getInt('replayViewCostOwn', 0)
    else:
        replayCost = SystemSettings.getInt('replayViewCostOther', 50)
    
    context = {
        'replayData': json.dumps(replayData),
        'metadata': metadata,
        'replayType': replayType,
        'profile': profile,
        'hasAccess': hasPaid,
        'replayId': replayId,
        'replayCost': replayCost,
        'isOwner': isOwner,
    }
    return render(request, 'matches/replayViewer.html', context)