from django.urls import path
from . import views

urlpatterns = [
    path('', views.homePage, name='homePage'),
    path('api/highScores', views.highScores, name='highScores'),
    path('api/saveScore', views.saveScore, name='saveScore'),
]
