#!/usr/bin/python
# Customer Service Agent for post-purchase support
import os
import grpc
from flask import Flask, request
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../recommendationservice'))
import demo_pb2
import demo_pb2_grpc

def create_app():
    app = Flask(__name__)

    def get_checkout_stub():
        channel = grpc.insecure_channel('checkoutservice:5050')
        return demo_pb2_grpc.CheckoutServiceStub(channel)

    def get_shipping_stub():
        channel = grpc.insecure_channel('shippingservice:50051')
        return demo_pb2_grpc.ShippingServiceStub(channel)

    @app.route('/order-status', methods=['GET'])
    def order_status():
        user_id = request.args.get('user_id')
        stub = get_checkout_stub()
        # TODO: Use PlaceOrderResponse or other API to get order status
        # For demo, return stub response
        return {'order_status': 'Order status feature coming soon.'}

    @app.route('/track-order', methods=['GET'])
    def track_order():
        tracking_id = request.args.get('tracking_id')
        stub = get_shipping_stub()
        # TODO: Use ShipOrderResponse or other API to get tracking info
        # For demo, return stub response
        return {'tracking_info': 'Tracking feature coming soon.'}

    @app.route('/faq', methods=['GET'])
    def faq():
        question = request.args.get('question')
        # Simple FAQ logic
        faqs = {
            'shipping': 'Shipping usually takes 3-5 business days.',
            'returns': 'You can return items within 30 days of purchase.',
            'payment': 'We accept all major credit cards and PayPal.'
        }
        answer = faqs.get(question.lower(), 'Sorry, I do not have an answer for that.')
        return {'answer': answer}

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=8090)
