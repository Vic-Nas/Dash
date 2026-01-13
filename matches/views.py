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
        
        return JsonResponse({
            'success': True,
            'won': won,
            'level': level,
            'botsEliminated': botsEliminated,
            'coinsEarned': float(coinsEarned),
            'newBalance': float(balanceAfter),
            'newHighestLevel': level > (profile.progressiveHighestLevel - level if won else profile.progressiveHighestLevel)
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
            
            match.totalPot = F('totalPot') + matchType.entryFee
            match.currentPlayers = F('currentPlayers') + 1
            match.save(update_fields=['totalPot', 'currentPlayers'])
            match.refresh_from_db()
            
            participation = MatchParticipation.objects.create(
                match=match,
                player=request.user,
                entryFeePaid=matchType.entryFee
            )
            
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
        
        if match.currentPlayers >= match.playersRequired:
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
    page = request.GET.get('page', 1)
    
    replays = []
    
    # Solo replays
    if mode in ['all', 'solo']:
        solo_runs = SoloRun.objects.filter(
            isPublic=True,
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
    
    # Progressive replays (only victories)
    if mode in ['all', 'progressive']:
        progressive_runs = ProgressiveRun.objects.filter(
            isPublic=True,
            replayData__isnull=False,
            won=True
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
            })
    
    # Multiplayer replays (winners only)
    if mode in ['all', 'multiplayer']:
        match_participations = MatchParticipation.objects.filter(
            isPublic=True,
            replayData__isnull=False,
            placement=1
        ).select_related('player', 'match', 'match__matchType').order_by('-match__completedAt')[:50]
        
        for participation in match_participations:
            replays.append({
                'type': 'multiplayer',
                'id': participation.id,
                'player': participation.player.username,
                'player_id': participation.player.id,
                'score': int(participation.coinReward),
                'score_label': f'{int(participation.coinReward)} coins won',
                'date': participation.match.completedAt,
                'time': participation.survivalTime or 0,
                'match_type': participation.match.matchType.name,
            })
    
    # Sort by date (most recent first)
    replays.sort(key=lambda x: x['date'], reverse=True)
    
    # Pagination
    paginator = Paginator(replays, 20)
    page_obj = paginator.get_page(page)
    
    context = {
        'replays': page_obj,
        'mode': mode,
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
        replay_type = data.get('type')
        replay_id = data.get('id')
        
        if not replay_type or not replay_id:
            return JsonResponse({
                'success': False,
                'error': 'Missing type or id'
            }, status=400)
        
        # Get replay and check ownership
        owner_id = None
        replay_exists = False
        replay_cost = 0
        replay_obj = None
        if replay_type == 'solo':
            run = SoloRun.objects.filter(id=replay_id, replayData__isnull=False).first()
            if run:
                owner_id = run.player.id
                replay_exists = True
                replay_obj = run
                replay_cost = SystemSettings.getInt('soloReplayCost', 1)
        elif replay_type == 'progressive':
            run = ProgressiveRun.objects.filter(id=replay_id, replayData__isnull=False).first()
            if run:
                owner_id = run.player.id
                replay_exists = True
                replay_obj = run
                replay_cost = SystemSettings.getInt('progressiveReplayCost', 2)
        elif replay_type == 'multiplayer':
            participation = MatchParticipation.objects.filter(id=replay_id, replayData__isnull=False).first()
            if participation:
                owner_id = participation.player.id
                replay_exists = True
                replay_obj = participation
                replay_cost = SystemSettings.getInt('multiplayerReplayCost', 3)
        
        if not replay_exists:
            return JsonResponse({'success': False, 'error': 'Replay not found'}, status=404)
        
        # Don't charge owner
        if owner_id == request.user.id:
            return JsonResponse({'success': True, 'paid': False, 'message': 'Owner, no charge'})
        
        # Check if already paid
        from .models import ReplayView
        already_paid = ReplayView.objects.filter(user=request.user.profile, replay_type=replay_type, replay_id=replay_id, paid=True).exists()
        if already_paid:
            return JsonResponse({'success': True, 'paid': False, 'message': 'Already paid'})
        
        # Deduct coins and record payment
        profile = request.user.profile
        profile = type(profile).objects.select_for_update().get(pk=profile.pk)
        balance_before = profile.coins
        if profile.coins < replay_cost:
            return JsonResponse({'success': False, 'error': 'Insufficient coins'}, status=402)
        profile.coins -= replay_cost
        profile.save(update_fields=['coins'])
        balance_after = profile.coins
        Transaction.objects.create(
            user=request.user,
            amount=-replay_cost,
            transactionType='REPLAY_VIEW',
            description=f'Paid to view {replay_type} replay #{replay_id}',
            balanceBefore=balance_before,
            balanceAfter=balance_after
        )
        ReplayView.objects.create(
            user=profile,
            replay_type=replay_type,
            replay_id=replay_id,
            paid=True
        )
        return JsonResponse({'success': True, 'paid': True, 'newBalance': float(balance_after)})
        
        if not replay_exists:
            return JsonResponse({
                'success': False,
                'error': 'Replay not found'
            }, status=404)
        
        # Check if user owns this replay
        is_owner = (owner_id == request.user.id)
        
        # Determine cost
        if is_owner:
            cost = Decimal(str(SystemSettings.getInt('replayViewCostOwn', 0)))
        else:
            cost = Decimal(str(SystemSettings.getInt('replayViewCostOther', 50)))
        
        # Deduct coins if cost > 0
        if cost > 0:
            with transaction.atomic():
                profile = request.user.profile
                profile = type(profile).objects.select_for_update().get(pk=profile.pk)
                
                if profile.coins < cost:
                    return JsonResponse({
                        'success': False,
                        'error': f'Insufficient coins. Need {cost}, have {profile.coins}'
                    }, status=400)
                
                balanceBefore = profile.coins
                profile.coins = F('coins') - cost
                profile.save(update_fields=['coins'])
                profile.refresh_from_db()
                balanceAfter = profile.coins
                
                # Create transaction record
                Transaction.objects.create(
                    user=request.user,
                    amount=-cost,
                    transactionType='EXTRA_LIFE',  # Reusing existing type or could add new one
                    description=f'Watched replay: {replay_type} #{replay_id}',
                    balanceBefore=balanceBefore,
                    balanceAfter=balanceAfter
                )
        
        return JsonResponse({
            'success': True,
            'redirect_url': f'/matches/replays/view/{replay_type}/{replay_id}/',
            'cost': float(cost)
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
def replayViewer(request, replay_type, replay_id):
    """Render replay viewer page"""
    replay_data = None
    metadata = {}
    
    if replay_type == 'solo':
        run = get_object_or_404(SoloRun, id=replay_id, replayData__isnull=False)
        replay_data = run.replayData
        metadata = {
            'type': 'Solo Mode',
            'player': run.player.username,
            'score': f'{run.wallsSurvived} walls survived',
            'time': f'{run.survivalTime}s',
            'date': run.endedAt,
        }
    elif replay_type == 'progressive':
        run = get_object_or_404(ProgressiveRun, id=replay_id, replayData__isnull=False)
        replay_data = run.replayData
        metadata = {
            'type': 'Progressive Mode',
            'player': run.player.username,
            'score': f'Level {run.level}' + (' (Victory)' if run.won else ' (Defeated)'),
            'time': f'{run.survivalTime}s',
            'date': run.endedAt,
        }
    elif replay_type == 'multiplayer':
        participation = get_object_or_404(MatchParticipation, id=replay_id, replayData__isnull=False)
        replay_data = participation.replayData
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
    already_paid = (profile.id == (metadata.get('player_id') if 'player_id' in metadata else None)) or ReplayView.objects.filter(user=profile, replay_type=replay_type, replay_id=replay_id, paid=True).exists()
    context = {
        'replay_data': json.dumps(replay_data),
        'metadata': metadata,
        'replay_type': replay_type,
        'profile': profile,
        'already_paid': already_paid,
        'replay_id': replay_id,
    }
    return render(request, 'matches/replayViewer.html', context)