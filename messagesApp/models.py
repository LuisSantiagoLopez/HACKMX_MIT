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
    CATEGORY_CHOICES = [
        ("Lácteos", "Lácteos"),
        ("Carnes y embutidos", "Carnes y embutidos"),
        ("Panadería", "Panadería"),
        ("Frutas", "Frutas"),
        ("Verduras", "Verduras"),
        ("Bebidas no alcohólicas", "Bebidas no alcohólicas"),
        ("Bebidas alcohólicas", "Bebidas alcohólicas"),
        ("Botanas", "Botanas"),
        ("Dulces", "Dulces"),
        ("Cereales", "Cereales"),
        ("Salsas y condimentos", "Salsas y condimentos"),
        ("Especias", "Especias"),
        ("Enlatados", "Enlatados"),
        ("Pastas", "Pastas"),
        ("Arroz y granos", "Arroz y granos"),
        ("Harinas", "Harinas"),
        ("Aceites", "Aceites"),
        ("Congelados", "Congelados"),
        ("Bebés", "Bebés"),
        ("Higiene personal", "Higiene personal"),
        ("Limpieza", "Limpieza"),
        ("Papel y desechables", "Papel y desechables"),
        ("Cuidado femenino", "Cuidado femenino"),
        ("Mascotas", "Mascotas"),
        ("Farmacia", "Farmacia"),
        ("Café y té", "Café y té"),
        ("Azúcar y endulzantes", "Azúcar y endulzantes"),
        ("Energéticas", "Energéticas"),
        ("Importados", "Importados"),
        ("Festivos", "Festivos"),
        ("Otros", "Otros"),
    ]

    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100,
        choices=CATEGORY_CHOICES,
        default="Otros")
    amount = models.CharField(max_length=20)

class AuxProdUser(models.Model):
    user_aux = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product_aux = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    buying_price = models.FloatField()

class Conversation(models.Model):
    thread_id = models.CharField(max_length=31)
    user_conversation = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

class Transaction(models.Model):
    product_transaction = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    user_transaction = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    buying_price_unitario = models.FloatField()
    selling_price_unitario = models.FloatField()
    time = models.DateTimeField(auto_now_add=True)
