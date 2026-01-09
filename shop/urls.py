from django.urls import path
from . import views

urlpatterns = [
    path('', views.shop, name='shop'),
    path('buy-skin/', views.buySkin, name='buySkin'),
    path('equip-skin/', views.equipSkin, name='equipSkin'),
    path('create-payment-intent/', views.createPaymentIntent, name='createPaymentIntent'),
    path('stripe-webhook/', views.stripeWebhook, name='stripeWebhook'),
]