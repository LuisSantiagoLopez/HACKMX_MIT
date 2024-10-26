from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    username = None
    email = None 
    phone = models.CharField(max_length=20, unique=True)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone

class Product(models.Model):
    barcode = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)

class AuxProdUser(models.Model):
    user_aux = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product_aux = models.ForeignKey(Product, on_delete=models.CASCADE)
    buying_price = models.FloatField()
    quantity = models.IntegerField(default=0)

class Conversation(models.Model):
    thread_id = models.CharField(max_length=31)
    user_conversation = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

class Transaction(models.Model):
    product_transaction = models.ForeignKey(Product, on_delete=models.CASCADE)
    selling_price = models.FloatField()
    time = models.DateTimeField(auto_now_add=True)
