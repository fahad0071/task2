from flask import Flask, request, jsonify, render_template
from spyne import Application, rpc, ServiceBase, Unicode, Double, Iterable, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
import os

# === Define SOAP Data Model ===
class Rate(ComplexModel):
    currency = Unicode
    rate = Double

# === SOAP Service Implementation ===
class CurrencyService(ServiceBase):
    fallback_rates = {
        'USD': 1.0,
        'EUR': 0.92,
        'GBP': 0.78,
        'JPY': 150.0
    }

    @rpc(Unicode, Unicode, Double, _returns=Double)
    def convert_currency(ctx, from_currency, to_currency, amount):
        if from_currency not in CurrencyService.fallback_rates or to_currency not in CurrencyService.fallback_rates:
            raise ValueError("Invalid currency code.")
        rate = CurrencyService.fallback_rates[to_currency] / CurrencyService.fallback_rates[from_currency]
        return round(amount * rate, 2)

    @rpc(Unicode, _returns=Iterable(Rate))
    def get_rates(ctx, base_currency):
        if base_currency not in CurrencyService.fallback_rates:
            raise ValueError("Invalid base currency")
        base = CurrencyService.fallback_rates[base_currency]
        for curr, rate in CurrencyService.fallback_rates.items():
            yield Rate(currency=curr, rate=round(rate / base, 3))

# === SOAP Application ===
soap_app = Application(
    [CurrencyService],
    tns="currency.soap",
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)
soap_wsgi_app = WsgiApplication(soap_app)

# === REST API ===
rest_app = Flask(__name__, template_folder='templates')

@rest_app.route('/')
def home():
    return render_template('index.html')

@rest_app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    from_currency = data.get('from_currency')
    to_currency = data.get('to_currency')
    amount = float(data.get('amount', 1.0))
    service = CurrencyService()
    result = service.convert_currency(None, from_currency, to_currency, amount)
    return jsonify({'from_currency': from_currency, 'to_currency': to_currency, 'amount': amount, 'result': result})

@rest_app.route('/rates', methods=['GET'])
def get_rates():
    base = request.args.get('base_currency', 'USD')
    service = CurrencyService()
    rates = list(service.get_rates(None, base))
    return jsonify({'base_currency': base, 'rates': {r.currency: r.rate for r in rates}})

# === Optional: local temperature + calculator (simple logic) ===
@rest_app.route('/convert_temp', methods=['POST'])
def convert_temp():
    data = request.json
    from_unit, to_unit, value = data['from_unit'], data['to_unit'], float(data['value'])
    if from_unit == 'C' and to_unit == 'F':
        result = (value * 9/5) + 32
    elif from_unit == 'F' and to_unit == 'C':
        result = (value - 32) * 5/9
    else:
        return jsonify({'error': 'Invalid conversion units'}), 400
    return jsonify({'from_unit': from_unit, 'to_unit': to_unit, 'value': value, 'result': round(result, 2)})

@rest_app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    op, a, b = data['operation'], int(data['intA']), int(data['intB'])
    if op == 'add':
        result = a + b
    elif op == 'subtract':
        result = a - b
    elif op == 'multiply':
        result = a * b
    elif op == 'divide':
        result = a / b if b != 0 else 'Infinity'
    else:
        return jsonify({'error': 'Invalid operation'}), 400
    return jsonify({'operation': op, 'intA': a, 'intB': b, 'result': result})

# === Combine SOAP and REST ===
app = DispatcherMiddleware(rest_app, {
    '/soap': soap_wsgi_app
})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server running on http://0.0.0.0:{port}")
    run_simple('0.0.0.0', port, app, use_reloader=False)
