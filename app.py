from flask import Flask, render_template, jsonify
import serial
import serial.tools.list_ports
import threading
import time
import re
import os

app = Flask(__name__)

# Global variables
latest_prediction = {
    'label': 'No detection yet',
    'confidence': 0,
    'all_predictions': {}
}
serial_connection = None
connection_status = {
    'connected': False,
    'error': None
}


def find_arduino_port():
    """Find the Arduino port automatically"""
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if 'USB' in port.description:
            return port.device
    return None


def parse_predictions(lines):
    """Parse multiple prediction lines and find the highest confidence"""
    predictions = {}
    max_confidence = 0
    max_label = None

    for line in lines:
        try:
            # Remove extra whitespace and strip brackets
            line = line.strip().strip('[]')
            if ':' in line and any(c.isdigit() for c in line):
                label, value = line.split(':')
                label = label.strip()
                # Convert string to float and handle percentage
                confidence = float(value.strip())
                predictions[label] = confidence

                # Track highest confidence
                if confidence > max_confidence:
                    max_confidence = confidence
                    max_label = label
        except:
            continue

    return {
        'label': max_label if max_label else 'No detection',
        'confidence': max_confidence,
        'all_predictions': predictions
    }


def read_serial():
    """Read from serial port and update latest prediction"""
    global latest_prediction, serial_connection, connection_status

    while True:
        if not connection_status['connected']:
            try:
                port = find_arduino_port()
                if not port:
                    connection_status['error'] = "No Arduino found. Please check the connection."
                    time.sleep(5)
                    continue

                if serial_connection is not None:
                    try:
                        serial_connection.close()
                    except:
                        pass

                serial_connection = serial.Serial(port, 115200, timeout=1)
                connection_status['connected'] = True
                connection_status['error'] = None
                print(f"Successfully connected to {port}")

            except serial.SerialException as e:
                connection_status['error'] = f"Serial connection error: {str(e)}"
                print(f"Connection failed: {str(e)}")
                time.sleep(5)
                continue

        try:
            if serial_connection and serial_connection.in_waiting:
                # Read multiple lines to collect all predictions
                lines = []
                while serial_connection.in_waiting:
                    line = serial_connection.readline().decode('utf-8').strip()
                    if line and ':' in line:
                        lines.append(line)

                if lines:
                    # Parse all predictions and update with highest confidence
                    latest_prediction = parse_predictions(lines)

        except Exception as e:
            print(f"Error reading serial: {e}")
            connection_status['connected'] = False
            connection_status['error'] = str(e)
            if serial_connection:
                try:
                    serial_connection.close()
                except:
                    pass
            serial_connection = None
            time.sleep(1)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_prediction')
def get_prediction():
    return jsonify({
        'prediction': latest_prediction,
        'status': connection_status
    })


def cleanup():
    """Cleanup function to close serial connection"""
    global serial_connection
    if serial_connection:
        try:
            serial_connection.close()
        except:
            pass


if __name__ == '__main__':
    # Register cleanup function
    import atexit

    atexit.register(cleanup)

    # Only start the serial thread in the main process
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        serial_thread = threading.Thread(target=read_serial, daemon=True)
        serial_thread.start()

    # Start Flask app
    app.run(debug=False)