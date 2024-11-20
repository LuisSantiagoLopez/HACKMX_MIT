import time
import json
import os
from dotenv import load_dotenv
from .models import Conversation, CustomUser, Product, AuxProdUser, Transaction
from django.utils import timezone
from datetime import timedelta
import logging
from openai import OpenAI
import re 
from rapidfuzz import process, fuzz
import unicodedata

logger = logging.getLogger(__name__)

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

client = OpenAI()

# LA CLASE PREDETERMINADA BOT TIENE EL FIN DE SIMPLIFICAR LA CREACIÓN DE UN ASISTENTE Y EL MANEJO DE SU THREAD.
# UN ASISTENTE ES UNA INSTANCIA DE UNA CONVERSACIÓN DE CHATGPT. UN THREAD ES LA MEMORIA DE UN ASISTENTE.
class Bot: 
    def __init__(self, user):
        self.client = client

        self.user = user

        # EL ASISTENTE SE CREARÁ CON UN THREAD ESPECÍFICO CON EL ID CORRESPONDIENTE AL NÚMERO DEL USUARIO. 
        self.thread = self.create_or_retrieve_thread()

        self.assistant_id = "asst_7gpT6VNSseo58Bh8nOwhqCCP"

    # ESTE MÉTODO EJECUTA UNA CONVERSACIÓN CON EL ASISTENTE.
    # SI ES LA PRIMERA VEZ QUE SE EJECUTA, SE ENVIARÁ EL PRIMER MENSAJE.
    def run(self, user_message):        
        # SE ENVÍA EL MENSAJE DEL USUARIO Y SE ESPERA A QUE EL ASISTENTE RESPONDA
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=user_message,
        )

        # INICIAMOS EL RUN DEL ASISTENTE
        run = self.client.beta.threads.runs.create(
           thread_id=self.thread.id,
           assistant_id=self.assistant_id,
        )

        # MANEJAMOS LAS ACCIONES REQUERIDAS POR EL ASISTENTE
        while run.status != 'completed':
            print(run.status)
            if run.status == 'requires_action':
                run = self.handle_requires_action(run)
            else:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread.id,
                    run_id=run.id,
                )
        
        # UNA VEZ QUE EL ASISTENTE HA RESPONDIDO, SE DEVUELVE EL ÚLTIMO MENSAJE
        messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
        last_message = messages.data[0].content[0].text.value

        return last_message

    def handle_requires_action(self, run):
        required_action = run.required_action
        if required_action.type == 'submit_tool_outputs':
            tool_calls = required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments
                tool_call_id = tool_call.id

                # Parse arguments safely
                args = json.loads(arguments)

                # Initialize output
                output = ""

                # Execute the corresponding function
                if function_name == "mandar_productos_inventario":
                    # Get user phone from arguments
                    products = args['products']
                    
                    # Process the batch and get output
                    output = process_product_batch({"products": products}, self.user)

                elif function_name == "vender_producto":
                    # Get arguments for selling product
                    products = args['products']
                    selling_price = args['selling_price']

                    # Sell the product and get output
                    output = sell_product({"productos": products, "precio_venta": selling_price}, self.user)

                elif function_name == "generar_reporte_ventas":
                    # Get timeframe and units from arguments
                    timeframe = args['timeframe']
                    units = args['units']

                    # Generate the sales report
                    output = generate_sales_report(self.user, timeframe, units) 

                # Add the tool output
                tool_outputs.append({
                    "tool_call_id": tool_call_id,
                    "output": output
                })

            # Submit the tool outputs to the assistant
            self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=self.thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )

        # Update the run status
        time.sleep(1)
        run = self.client.beta.threads.runs.retrieve(
            thread_id=self.thread.id,
            run_id=run.id,
        )
        return run


    # SI YA EXISTÍA UNA CONVERSACIÓN PREVIA CON ESTE NÚMERO, SE DEVUELVE EL THREAD.
    # SI NO, SE CREA UN NUEVO THREAD.
    def create_or_retrieve_thread(self):
        try:
            # Try to retrieve the existing conversation for the user
            conversation = Conversation.objects.filter(user_conversation=self.user).first()

            if conversation:
                logger.debug(f"Conversation found for user {self.user.phone}. Thread ID: {conversation.thread_id}")
            else:
                logger.debug(f"No conversation found for user {self.user.phone}")

            if conversation and conversation.thread_id:
                # If a conversation exists, retrieve the thread using its thread_id
                logger.debug(f"Retrieving thread with ID: {conversation.thread_id}")
                thread = self.client.beta.threads.retrieve(conversation.thread_id)
            else:
                # If no conversation exists, create a new thread
                logger.debug(f"Creating a new thread for user {self.user.phone}")
                thread = self.client.beta.threads.create()
                thread_id = thread.id

                # Save the new thread in the Conversation model
                Conversation.objects.create(
                    thread_id=thread_id,
                    user_conversation=self.user
                )
                logger.debug(f"New conversation created with thread ID: {thread_id}")

            return thread

        except CustomUser.DoesNotExist:
            logger.error("User with the given phone number does not exist.")
            return None

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return None


def process_product_batch(data, user):
    products = data.get('products')
    if not products:
        return "Products must be provided. Status: 400"

    for product_data in products:
        # Obtener datos del producto
        name = product_data.get('name')
        brand = product_data.get('brand')
        category = product_data.get('category', "Otros")
        amount = product_data.get('amount')
        buying_price = float(product_data.get('buying_price', 0))
        quantity = int(product_data.get('quantity', 0))

        # Validar que los campos requeridos sean válidos
        if not name or not category or not amount or quantity <= 0:
            continue

        # Obtener o crear el producto principal
        product, _ = Product.objects.get_or_create(
            name=name,
            brand=brand,
            amount=amount,
            defaults={
                'category': category,
            }
        )

        # Obtener o crear el registro en AuxProdUser
        aux_prod_user, created = AuxProdUser.objects.get_or_create(
            user_aux=user,
            product_aux=product,
            defaults={
                'user_aux': user,
                'product_aux': product,
                'quantity': quantity,
                'buying_price': buying_price
            }
        )

        if not created:
            # Actualizar cantidad y precio de compra
            aux_prod_user.quantity += quantity
            aux_prod_user.save()

    return "Batch processed successfully. Status: 201"


def normalize_text(text):
    if not text:
        return ''
    # Eliminar acentos y caracteres especiales
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    # Convertir a minúsculas
    text = text.lower()
    # Eliminar caracteres especiales como guiones, apóstrofes, puntos, comas, etc.
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # Eliminar espacios adicionales
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def sell_product(data, user):
    logger.debug("Iniciando la función sell_product")
    productos = data.get('productos')
    precio_venta = data.get('precio_venta')
    logger.debug(f"Datos recibidos - precio_venta: {precio_venta}, productos: {productos}")

    if not productos or precio_venta is None:
        logger.error("No se proporcionaron 'productos' o 'precio_venta'")
        return "Debe proporcionar 'productos' y 'precio_venta'. Status: 400"

    precio_venta = float(precio_venta)
    mensajes = []

    for producto_data in productos:
        logger.debug(f"Procesando producto: {producto_data}")
        nombre = producto_data.get('nombre')
        marca = producto_data.get('marca')
        categoría = producto_data.get('categoría')
        unidad_medida = producto_data.get('unidad_medida')
        cantidad = int(producto_data.get('cantidad', 1))

        # Validar que los campos requeridos estén presentes y correctos
        if not all([nombre, categoría, unidad_medida, marca is not None]) or cantidad <= 0:
            logger.error(f"Datos inválidos para el producto '{nombre}': {producto_data}")
            mensajes.append(f"El producto '{nombre}' no tiene todos los datos requeridos o los valores son inválidos. No se procesó la venta de este producto.")
            continue

        # Normalizar y combinar nombre y unidad de medida
        nombre_normalizado = normalize_text(nombre)
        unidad_medida_normalizada = normalize_text(unidad_medida)
        nombre_unidad = f"{nombre_normalizado} {unidad_medida_normalizada}"
        marca_normalizada = normalize_text(marca)
        categoría_normalizada = normalize_text(categoría)
        logger.debug(f"Datos normalizados - nombre_unidad: {nombre_unidad}, marca: {marca_normalizada}, categoría: {categoría_normalizada}")

        # Obtener productos en la categoría
        productos_en_categoria = AuxProdUser.objects.filter(
            user_aux=user,
            product_aux__category__iexact=categoría
        ).select_related('product_aux')

        logger.debug(f"Productos encontrados en la categoría '{categoría}' para el usuario '{user}': {productos_en_categoria.count()}")

        if not productos_en_categoria.exists():
            logger.error(f"No se encontraron productos en la categoría '{categoría}' asociados al usuario '{user}'")
            mensajes.append(f"No se encontraron productos en la categoría '{categoría}' asociados a tu inventario.")
            continue

        # Crear listas de nombres (nombre + unidad) y marcas normalizados
        nombres_unidad_productos = []
        marcas_productos = []
        productos_lista = []

        for producto in productos_en_categoria:
            nombre_prod_norm = normalize_text(producto.name)
            unidad_medida_prod_norm = normalize_text(producto.amount)
            nombre_unidad_prod = f"{nombre_prod_norm} {unidad_medida_prod_norm}"
            marca_prod_norm = normalize_text(producto.brand)
            nombres_unidad_productos.append(nombre_unidad_prod)
            marcas_productos.append(marca_prod_norm)
            productos_lista.append(producto)

        # Encontrar el producto con el nombre y unidad más similar
        match = process.extractOne(nombre_unidad, nombres_unidad_productos, scorer=fuzz.token_sort_ratio)
        logger.debug(f"Resultado del matching difuso para '{nombre_unidad}': {match}")

        if match and match[1] >= 80:  # Umbral de similitud del 80%
            idx = nombres_unidad_productos.index(match[0])
            producto_encontrado = productos_lista[idx]
            logger.debug(f"Producto encontrado: {producto_encontrado.name} (ID: {producto_encontrado.id}), Unidad: {producto_encontrado.amount}, con similitud de {match[1]}%")

            # Si se proporcionó marca, verificar similitud de marca
            if marca_normalizada:
                ratio_marca = fuzz.token_sort_ratio(marca_normalizada, marcas_productos[idx])
                logger.debug(f"Similitud de marca para '{marca_normalizada}': {ratio_marca}%")
                if ratio_marca < 80:
                    logger.error(f"La marca '{marca}' no coincide suficientemente con '{producto_encontrado.brand}'")
                    mensajes.append(f"No se encontró una marca similar a '{marca}' para el producto '{nombre}'.")
                    continue
        else:
            logger.error(f"No se encontró un producto similar a '{nombre}' con unidad '{unidad_medida}' en la categoría '{categoría}'")
            mensajes.append(f"No se encontró un producto similar a '{nombre}' con unidad '{unidad_medida}' en la categoría '{categoría}'.")
            continue

        # Buscar el AuxProdUser asociado al usuario para obtener 'buying_price'
        try:
            aux_prod_user = AuxProdUser.objects.get(product_aux=producto_encontrado, user_aux=user)
            logger.debug(f"Producto en inventario del usuario. Cantidad disponible: {aux_prod_user.quantity}")
        except AuxProdUser.DoesNotExist:
            logger.error(f"El usuario no tiene el producto '{producto_encontrado.name}' en su inventario")
            mensajes.append(f"No tienes disponible el producto '{producto_encontrado.name}' para vender.")
            continue

        if aux_prod_user.quantity < cantidad:
            logger.error(f"Cantidad insuficiente del producto '{producto_encontrado.name}'. Disponible: {aux_prod_user.quantity}, solicitada: {cantidad}")
            mensajes.append(f"No hay suficientes unidades del producto '{producto_encontrado.name}' para vender. Disponibles: {aux_prod_user.quantity}.")
            continue

        # Obtener el precio de compra del AuxProdUser
        precio_compra = aux_prod_user.buying_price
        logger.debug(f"Precio de compra obtenido del AuxProdUser: {precio_compra}")

        # Reducir la cantidad del producto
        aux_prod_user.quantity -= cantidad
        logger.debug(f"Reduciendo cantidad del producto '{producto_encontrado.name}' en el inventario del usuario. Nueva cantidad: {aux_prod_user.quantity}")

        # Eliminar el AuxProdUser si la cantidad llega a 0
        if aux_prod_user.quantity == 0:
            aux_prod_user.delete()
            logger.debug(f"El producto '{producto_encontrado.name}' se ha agotado en el inventario del usuario y se eliminó el registro de AuxProdUser")
        else:
            aux_prod_user.save()
            logger.debug(f"Actualizada la cantidad del producto '{producto_encontrado.name}' en el inventario del usuario")

        # Registrar la transacción
        transaction = Transaction.objects.create(
            product_transaction=producto_encontrado,
            user_transaction=user,
            selling_price_unitario=precio_venta,
            buying_price_unitario=precio_compra,
            quantity=cantidad
        )
        logger.debug(f"Transacción registrada: ID {transaction.id} - Producto '{producto_encontrado.name}', Cantidad: {cantidad}, Precio venta unitario: {precio_venta}")

        mensajes.append(f"Producto '{producto_encontrado.name}' vendido con éxito. Cantidad vendida: {cantidad}.")

    if mensajes:
        logger.debug("Proceso de venta completado con mensajes")
        return "\n".join(mensajes) + " Status: 201"
    else:
        logger.error("No se pudo procesar ninguna venta")
        return "No se pudo procesar ninguna venta. Verifique los datos proporcionados. Status: 400"

def generate_sales_report(user, timeframe, units):
    logger.debug("Iniciando la función generate_sales_report")
    logger.debug(f"Datos recibidos - user: {user}, timeframe: {timeframe}, units: {units}")

    # Validar el timeframe
    now = timezone.now()
    if timeframe == 'days':
        start_date = now - timedelta(days=units)
    elif timeframe == 'weeks':
        start_date = now - timedelta(weeks=units)
    elif timeframe == 'months':
        start_date = now - timedelta(days=30 * units)
    else:
        logger.error("Periodo de tiempo inválido")
        return "Periodo de tiempo inválido. Use 'days', 'weeks' o 'months'. Status: 400"

    # Filtrar transacciones por usuario y fecha
    transactions = Transaction.objects.filter(
        user_transaction=user,
        time__gte=start_date
    )
    logger.debug(f"Transacciones encontradas: {transactions.count()}")

    if not transactions.exists():
        logger.debug("No se encontraron transacciones en el periodo especificado")
        return f"No se encontraron transacciones para el usuario {user} en el periodo especificado. Status: 404"

    # Calcular métricas
    total_products_sold = sum(transaction.quantity for transaction in transactions)
    logger.debug(f"Total de productos vendidos: {total_products_sold}")

    total_revenue = sum(transaction.selling_price_unitario * transaction.quantity for transaction in transactions)
    logger.debug(f"Ingresos totales: {total_revenue}")

    total_profit = sum(
        (transaction.selling_price_unitario - transaction.buying_price_unitario) * transaction.quantity
        for transaction in transactions
    )
    logger.debug(f"Ganancia total: {total_profit}")

    # Generar el reporte como string
    report = (
        f"Reporte de Ventas:\n"
        f"Usuario: {user}\n"
        f"Periodo: Últimos {units} {timeframe}\n"
        f"Total de productos vendidos: {total_products_sold}\n"
        f"Ingresos totales: ${total_revenue:.2f}\n"
        f"Ganancia total: ${total_profit:.2f}\n"
        f"Status: 200 - Reporte generado exitosamente."
    )
    logger.debug(f"Reporte generado: {report}")

    return report