from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import playerScore
import json


def homePage(request):
    return render(request, 'game/index.html')


@require_http_methods(["GET"])
def highScores(request):
    top = list(playerScore.objects.order_by('-scoreValue', 'createdAt').values('playerName', 'scoreValue')[:10])
    return JsonResponse({"highScores": top})


@require_http_methods(["POST"])
@csrf_exempt
def saveScore(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
        playerName = data.get('playerName', '').strip()[:50] or 'Anonymous'
        scoreValue = int(data.get('scoreValue', 0))
        if scoreValue < 0:
            scoreValue = 0
        playerScore.objects.create(playerName=playerName, scoreValue=scoreValue)
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
