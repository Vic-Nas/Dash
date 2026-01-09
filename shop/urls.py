from django.urls import path
from . import views

urlpatterns = [
    path('', views.shop, name='shop'),
    path('create-payment-intent/', views.createPaymentIntent, name='createPaymentIntent'),
    path('stripe-webhook/', views.stripeWebhook, name='stripeWebhook'),
]