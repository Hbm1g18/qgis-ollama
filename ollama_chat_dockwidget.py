import os
import requests
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsProject

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ollama_chat_dockwidget_base.ui'))


class OllamaChatDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(OllamaChatDockWidget, self).__init__(parent)
        self.setupUi(self)

        # Connect button click to function
        self.pushButton_fetch.clicked.connect(self.fetch_api_data)

    def fetch_api_data(self):
        """Send user prompt to Ollama API with project context and display response."""
        user_prompt = self.lineEdit_apiUrl.text().strip()

        # Get all loaded layers in QGIS
        layers = QgsProject.instance().mapLayers().values()

        if not user_prompt:
            self.textEdit_response.setPlainText("Please enter a valid prompt.")
            return

        # Construct context about the current QGIS project
        context_info = "Here is some context regarding the current project:\nLayers:\n"

        for layer in layers:
            layer_type = "Unknown"
            if layer.type() == 0:
                layer_type = "Vector Layer"
            elif layer.type() == 1:
                layer_type = "Raster Layer"

            context_info += f"- {layer.name()}: {layer_type} (CRS: {layer.crs().authid()})\n"

        # Updated Prompt
        full_prompt = f"""
{context_info}

## Task:
{user_prompt}

## Instructions:
- Generate a Python script that runs **directly** in the QGIS Python console.
- Use `processing.run("native:xyz", {{params}})` for processing tools.
- Ensure outputs are stored in `QgsProject.instance()`.
- Use `context = QgsProcessingContext()` and `feedback = QgsProcessingFeedback()`.
- Do **not** use `iface.activeLayer()` unless necessary.
- Format the response as a Python **code block** with correct indentation.

## Example Format:
```python
import processing
from qgis.core import QgsProject, QgsProcessingContext, QgsProcessingFeedback

context = QgsProcessingContext()
feedback = QgsProcessingFeedback()

params = {{
    'INPUT': 'path/to/input.shp',
    'OUTPUT': 'memory:'
}}

result = processing.run('native:mergevectorlayers', params, context=context, feedback=feedback)

output_layer = result['OUTPUT']
QgsProject.instance().addMapLayer(output_layer)
Please follow this structure exactly. """
        try:
            server_url = "http://192.168.1.89:11434/api/generate"
            model = "qwen2.5:3b"

            # Prepare the payload
            payload = {
                "model": model,
                "prompt": full_prompt,
                "stream": False
            }

            # Send request
            response = requests.post(server_url, json=payload)
            response.raise_for_status()

            # Display the response
            if response.status_code == 200:
                response_data = response.json()
                self.textEdit_response.setPlainText(response_data.get("response", "No response received."))
            else:
                self.textEdit_response.setPlainText(f"Failed to get a response. Status code: {response.status_code}")

        except requests.RequestException as e:
            self.textEdit_response.setPlainText(f"Error communicating with Ollama: {str(e)}")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
