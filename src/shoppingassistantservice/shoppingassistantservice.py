#!/usr/bin/python
#
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import grpc
import sys
sys.path.append(os.path.dirname(__file__))
import demo_pb2
import demo_pb2_grpc

from google.cloud import secretmanager_v1
from urllib.parse import unquote
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from flask import Flask, request

from langchain_google_alloydb_pg import AlloyDBEngine, AlloyDBVectorStore

PROJECT_ID = os.environ["PROJECT_ID"]
REGION = os.environ["REGION"]
ALLOYDB_DATABASE_NAME = os.environ["ALLOYDB_DATABASE_NAME"]
ALLOYDB_TABLE_NAME = os.environ["ALLOYDB_TABLE_NAME"]
ALLOYDB_CLUSTER_NAME = os.environ["ALLOYDB_CLUSTER_NAME"]
ALLOYDB_INSTANCE_NAME = os.environ["ALLOYDB_INSTANCE_NAME"]
ALLOYDB_SECRET_NAME = os.environ["ALLOYDB_SECRET_NAME"]

secret_manager_client = secretmanager_v1.SecretManagerServiceClient()
secret_name = secret_manager_client.secret_version_path(project=PROJECT_ID, secret=ALLOYDB_SECRET_NAME, secret_version="latest")
secret_request = secretmanager_v1.AccessSecretVersionRequest(name=secret_name)
secret_response = secret_manager_client.access_secret_version(request=secret_request)
PGPASSWORD = secret_response.payload.data.decode("UTF-8").strip()

engine = AlloyDBEngine.from_instance(
    project_id=PROJECT_ID,
    region=REGION,
    cluster=ALLOYDB_CLUSTER_NAME,
    instance=ALLOYDB_INSTANCE_NAME,
    database=ALLOYDB_DATABASE_NAME,
    user="postgres",
    password=PGPASSWORD
)

# Create a synchronous connection to our vectorstore
vectorstore = AlloyDBVectorStore.create_sync(
    engine=engine,
    table_name=ALLOYDB_TABLE_NAME,
    embedding_service=GoogleGenerativeAIEmbeddings(model="models/embedding-001"),
    id_column="id",
    content_column="description",
    embedding_column="product_embedding",
    metadata_columns=["id", "name", "categories"]
)

def create_app():
    def get_recommendation_stub():
        channel = grpc.insecure_channel('recommendationservice:8080')
        return demo_pb2_grpc.RecommendationServiceStub(channel)

    def get_cart_stub():
        channel = grpc.insecure_channel('cartservice:7070')
        return demo_pb2_grpc.CartServiceStub(channel)
    app = Flask(__name__)

    def get_productcatalog_stub():
        # TODO: Use service discovery/env for address
        channel = grpc.insecure_channel('productcatalogservice:3550')
        return demo_pb2_grpc.ProductCatalogServiceStub(channel)

    @app.route("/conversation", methods=['POST'])
    def conversation():
        user_id = request.json.get('user_id')
        message = request.json.get('message')
        # TODO: Integrate LLM for natural conversation
        return {"reply": f"Echo: {message}"}

    @app.route("/search", methods=['POST'])
    def search():
        query = request.json.get('query')
        stub = get_productcatalog_stub()
        req = demo_pb2.SearchProductsRequest(query=query)
        resp = stub.SearchProducts(req)
        products = [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "picture": p.picture,
                "categories": list(p.categories)
            } for p in resp.results
        ]
        return {"results": products}

    @app.route("/recommend", methods=['POST'])
    def recommend():
        user_id = request.json.get('user_id')
    stub = get_recommendation_stub()
    # For demo, get all products and recommend for user
    product_stub = get_productcatalog_stub()
    products_resp = product_stub.ListProducts(demo_pb2.Empty())
    product_ids = [p.id for p in products_resp.products]
    req = demo_pb2.ListRecommendationsRequest(user_id=user_id, product_ids=product_ids)
    resp = stub.ListRecommendations(req)
    return {"product_ids": list(resp.product_ids)}

    @app.route("/cart/add", methods=['POST'])
    def add_to_cart():
        user_id = request.json.get('user_id')
        product_id = request.json.get('product_id')
        quantity = request.json.get('quantity', 1)
    stub = get_cart_stub()
    item = demo_pb2.CartItem(product_id=product_id, quantity=quantity)
    req = demo_pb2.AddItemRequest(user_id=user_id, item=item)
    stub.AddItem(req)
    return {"success": True, "message": "Added to cart"}

    @app.route("/cart/view", methods=['GET'])
    def view_cart():
        user_id = request.args.get('user_id')
    stub = get_cart_stub()
    req = demo_pb2.GetCartRequest(user_id=user_id)
    resp = stub.GetCart(req)
    product_ids = [item.product_id for item in resp.items]
    return {"product_ids": product_ids}

    @app.route("/personalize", methods=['GET'])
    def personalize():
        user_id = request.args.get('user_id')
    # Stub: personalize by returning cart items
    stub = get_cart_stub()
    req = demo_pb2.GetCartRequest(user_id=user_id)
    resp = stub.GetCart(req)
    product_ids = [item.product_id for item in resp.items]
    return {"product_ids": product_ids}


    @app.route("/", methods=['POST'])
    def talkToGemini():
        print("Beginning RAG call")
        prompt = request.json['message']
        prompt = unquote(prompt)

        # Step 1 – Get a room description from Gemini-vision-pro
        llm_vision = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": "You are a professional interior designer, give me a detailed decsription of the style of the room in this image",
                },
                {"type": "image_url", "image_url": request.json['image']},
            ]
        )
        response = llm_vision.invoke([message])
        print("Description step:")
        print(response)
        description_response = response.content

        # Step 2 – Similarity search with the description & user prompt
        vector_search_prompt = f""" This is the user's request: {prompt} Find the most relevant items for that prompt, while matching style of the room described here: {description_response} """
        print(vector_search_prompt)

        docs = vectorstore.similarity_search(vector_search_prompt)
        print(f"Vector search: {description_response}")
        print(f"Retrieved documents: {len(docs)}")
        #Prepare relevant documents for inclusion in final prompt
        relevant_docs = ""
        for doc in docs:
            doc_details = doc.to_json()
            print(f"Adding relevant document to prompt context: {doc_details}")
            relevant_docs += str(doc_details) + ", "

        # Step 3 – Tie it all together by augmenting our call to Gemini-pro
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
        design_prompt = (
            f" You are an interior designer that works for Online Boutique. You are tasked with providing recommendations to a customer on what they should add to a given room from our catalog. This is the description of the room: \n"
            f"{description_response} Here are a list of products that are relevant to it: {relevant_docs} Specifically, this is what the customer has asked for, see if you can accommodate it: {prompt} Start by repeating a brief description of the room's design to the customer, then provide your recommendations. Do your best to pick the most relevant item out of the list of products provided, but if none of them seem relevant, then say that instead of inventing a new product. At the end of the response, add a list of the IDs of the relevant products in the following format for the top 3 results: [<first product ID>], [<second product ID>], [<third product ID>] ")
        print("Final design prompt: ")
        print(design_prompt)
        design_response = llm.invoke(
            design_prompt
        )

        data = {'content': design_response.content}
        return data

    return app

if __name__ == "__main__":
    # Create an instance of flask server when called directly
    app = create_app()
    app.run(host='0.0.0.0', port=8080)
