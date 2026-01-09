from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from .models import GlobalChatMessage, DirectMessage
import json


@login_required
def globalChat(request):
    """Global chat room"""
    messages = GlobalChatMessage.objects.select_related('user').all()[:100]
    
    context = {
        'messages': messages,
        'profile': request.user.profile,
    }
    return render(request, 'chat/global_chat.html', context)


@login_required
def pollGlobalMessages(request):
    """Poll for new messages after a given ID"""
    afterId = int(request.GET.get('after', 0))
    
    messages = GlobalChatMessage.objects.filter(id__gt=afterId).select_related('user').order_by('id')[:50]
    
    messagesList = [{
        'id': msg.id,
        'username': msg.user.username,
        'message': msg.message,
        'time': msg.createdAt.strftime('%H:%M')
    } for msg in messages]
    
    return JsonResponse({
        'success': True,
        'messages': messagesList
    })


@login_required
@require_POST
def sendGlobalMessage(request):
    """Send message to global chat"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        
        if not message or len(message) > 500:
            return JsonResponse({'success': False, 'error': 'Invalid message'}, status=400)
        
        chatMessage = GlobalChatMessage.objects.create(
            user=request.user,
            message=message
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': chatMessage.id,
                'username': request.user.username,
                'message': chatMessage.message,
                'createdAt': chatMessage.createdAt.isoformat()
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def directMessages(request):
    """View all conversations"""
    User = get_user_model()
    
    # Get all users current user has messaged with
    sentTo = DirectMessage.objects.filter(sender=request.user).values_list('recipient_id', flat=True).distinct()
    receivedFrom = DirectMessage.objects.filter(recipient=request.user).values_list('sender_id', flat=True).distinct()
    
    conversationUserIds = set(sentTo) | set(receivedFrom)
    conversationUsers = User.objects.filter(id__in=conversationUserIds)
    
    # Get unread count for each conversation
    conversations = []
    for user in conversationUsers:
        unreadCount = DirectMessage.objects.filter(
            sender=user,
            recipient=request.user,
            isRead=False
        ).count()
        
        lastMessage = DirectMessage.objects.filter(
            Q(sender=request.user, recipient=user) | 
            Q(sender=user, recipient=request.user)
        ).first()
        
        conversations.append({
            'user': user,
            'unreadCount': unreadCount,
            'lastMessage': lastMessage
        })
    
    # Sort by last message time
    conversations.sort(key=lambda x: x['lastMessage'].createdAt if x['lastMessage'] else None, reverse=True)
    
    context = {
        'conversations': conversations,
        'profile': request.user.profile,
    }
    return render(request, 'chat/direct_messages.html', context)


@login_required
def conversation(request, userId):
    """View conversation with specific user"""
    User = get_user_model()
    otherUser = get_object_or_404(User, id=userId)
    
    # Mark all messages from other user as read
    DirectMessage.objects.filter(
        sender=otherUser,
        recipient=request.user,
        isRead=False
    ).update(isRead=True)
    
    # Get all messages between these two users
    messages = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=otherUser) |
        Q(sender=otherUser, recipient=request.user)
    ).select_related('sender', 'recipient').order_by('createdAt')[:100]
    
    context = {
        'otherUser': otherUser,
        'messages': messages,
        'profile': request.user.profile,
    }
    return render(request, 'chat/conversation.html', context)


@login_required
def pollConversationMessages(request, userId):
    """Poll for new messages after a given ID"""
    User = get_user_model()
    otherUser = get_object_or_404(User, id=userId)
    afterId = int(request.GET.get('after', 0))
    
    messages = DirectMessage.objects.filter(
        Q(sender=request.user, recipient=otherUser) |
        Q(sender=otherUser, recipient=request.user),
        id__gt=afterId
    ).select_related('sender').order_by('id')[:50]
    
    messagesList = [{
        'id': msg.id,
        'sender': msg.sender.username,
        'message': msg.message,
        'time': msg.createdAt.strftime('%H:%M'),
        'isSent': msg.sender == request.user
    } for msg in messages]
    
    return JsonResponse({
        'success': True,
        'messages': messagesList
    })


@login_required
@require_POST
def sendDirectMessage(request):
    """Send direct message to user"""
    try:
        data = json.loads(request.body)
        recipientId = data.get('recipientId')
        message = data.get('message', '').strip()
        
        if not message or len(message) > 1000:
            return JsonResponse({'success': False, 'error': 'Invalid message'}, status=400)
        
        User = get_user_model()
        recipient = get_object_or_404(User, id=recipientId)
        
        if recipient == request.user:
            return JsonResponse({'success': False, 'error': 'Cannot message yourself'}, status=400)
        
        directMessage = DirectMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            message=message
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': directMessage.id,
                'sender': request.user.username,
                'message': directMessage.message,
                'createdAt': directMessage.createdAt.isoformat()
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def unreadCount(request):
    """Get unread message count"""
    count = DirectMessage.objects.filter(
        recipient=request.user,
        isRead=False
    ).count()
    
    return JsonResponse({'unreadCount': count})