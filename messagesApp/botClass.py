import time
import json
import os
from dotenv import load_dotenv
from .models import Conversation, CustomUser, Product, AuxProdUser, Transaction
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import logging
from openai import OpenAI

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

        self.assistant_id = "asst_Q6r8BuVcR0w3z89Q7R5xUWyt"

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
                if function_name == "process_product_batch":
                    # Get user phone from arguments
                    products = args['products']
                    
                    # Process the batch and get output
                    output = process_product_batch({"products": products}, self.user)

                elif function_name == "sell_product":
                    # Get arguments for selling product
                    barcode = args['barcode']
                    selling_price = args['selling_price']

                    # Sell the product and get output
                    output = sell_product({"barcode": barcode, "selling_price": selling_price}, self.user)

                elif function_name == "generate_sales_report":
                    # Get timeframe and units from arguments
                    timeframe = args['timeframe']
                    units = args['units']

                    # Generate the sales report
                    report = generate_sales_report(self.user, timeframe, units)  # Corrected order
                    output = json.dumps(report)

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
        barcode = product_data.get('barcode')
        barcode = int(barcode)
        name = product_data.get('name')
        buying_price = float(product_data.get('buying_price', 0))
        quantity = int(product_data.get('quantity', 0))

        if not barcode or not name or quantity <= 0:
            continue

        # Get or create the product
        product, _ = Product.objects.get_or_create(
            barcode=barcode,
            defaults={'name': name}
        )

        # Get or create AuxProdUser without buying_price in lookup
        aux_prod_user, created = AuxProdUser.objects.get_or_create(
            user_aux=user,
            product_aux=product,
            defaults={
                'buying_price': buying_price,
                'quantity': quantity
            }
        )

        if not created:
            # Update quantity and buying_price as needed
            aux_prod_user.quantity += quantity
            aux_prod_user.buying_price = buying_price  # Optional
            aux_prod_user.save()

    return "Batch processed successfully. Status: 201"

def sell_product(data, user):
    barcode = data.get('barcode')
    selling_price = data.get('selling_price')

    if not barcode or selling_price is None:
        return "Both barcode and selling price must be provided. Status: 400"

    barcode = int(barcode)
    selling_price = float(selling_price)

    # Get the product
    try:
        product = Product.objects.get(barcode=barcode)
    except Product.DoesNotExist:
        return "Product not found. Status: 404"

    # Get the AuxProdUser for the user and product
    try:
        aux_prod_user = AuxProdUser.objects.get(
            product_aux=product,
            user_aux=user
        )
    except AuxProdUser.DoesNotExist:
        return "No available product for the user to sell. Status: 404"

    if aux_prod_user.quantity <= 0:
        return "No available product for the user to sell. Status: 404"

    # Decrease quantity
    aux_prod_user.quantity -= 1

    # Delete the AuxProdUser instance if quantity is zero
    if aux_prod_user.quantity == 0:
        aux_prod_user.delete()
        message = "Product sold successfully. You no longer have this product in your inventory. Status: 201"
    else:
        aux_prod_user.save()
        message = "Product sold successfully. Status: 201"

    # Register the transaction
    Transaction.objects.create(
        product_transaction=product,
        user_transaction=user,
        selling_price=selling_price
    )

    return message


def generate_sales_report(user, timeframe, units):
    # Calculate the start date based on the timeframe
    now = timezone.now()
    if timeframe == 'days':
        start_date = now - timedelta(days=units)
    elif timeframe == 'weeks':
        start_date = now - timedelta(weeks=units)
    elif timeframe == 'months':
        start_date = now - timedelta(days=30 * units)
    else:
        return "Invalid timeframe. Use 'days', 'weeks', or 'months'. Status: 400"

    # Filter transactions for the user within the specified timeframe
    transactions = Transaction.objects.filter(
        user_transaction=user,
        time__gte=start_date
    )

    total_products_sold = transactions.count()
    total_revenue = sum(transaction.selling_price for transaction in transactions)

    total_profit = sum(
        transaction.selling_price - aux_prod.buying_price
        for transaction in transactions
        if (aux_prod := AuxProdUser.objects.filter(
            product_aux=transaction.product_transaction,
            user_aux=user
        ).first())
    )

    return (f"Total productos vendidos: {total_products_sold}, "
            f"Total ingresado: {total_revenue}, "
            f"Total de ganancias: {total_profit}. Status: 200")
