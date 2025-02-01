import os
import requests
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsProject, QgsApplication

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
        self.pushButton_execute.clicked.connect(self.execute_generated_code)
        self.pushButton_discussask.clicked.connect(self.discuss)

    def discuss(self):
        user_prompt = self.lineEdit_discussprompt.text().strip()

        full_prompt = f"""
            You are a useful tool designed for discussion of Geographic information software, in this case, QGIS. Please provide helpful information about the following prompt in a geospatial minded way:\n
            {user_prompt}
        """

        try:
            server_url = "http://192.168.1.89:11434/api/generate"
            model = "qwen2.5-coder:7b"

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
                self.textEdit_discussresponse.setPlainText(response_data.get("response", "No response received."))
            else:
                self.textEdit_discussresponse.setPlainText(f"Failed to get a response. Status code: {response.status_code}")

        except requests.RequestException as e:
            self.textEdit_discussresponse.setPlainText(f"Error communicating with Ollama: {str(e)}")

    def fetch_available_algorithms(self):
        # Collect the list of available algorithms, filtered by provider
        available_algorithms = []
        for alg in QgsApplication.processingRegistry().algorithms():
                available_algorithms.append({
                    "provider": alg.provider().name(),
                    "name": alg.name(),
                    "displayName": alg.displayName()
                })
        return available_algorithms

    def fetch_api_data(self):
        """Send user prompt to Ollama API with project context and display response."""
        user_prompt = self.lineEdit_apiUrl.text().strip()

        # Construct context about the current QGIS project
        context_info = "Here is some context regarding the current project:\nLayers:\n"

        # Get all loaded layers in QGIS
        layers = QgsProject.instance().mapLayers().values()

        layer_ids = []
        for layer in layers:
            layer_type = "Unknown"
            if layer.type() == 0:
                layer_type = "Vector Layer"
            elif layer.type() == 1:
                layer_type = "Raster Layer"

            # Collecting layer IDs for use in the processing script
            layer_ids.append(layer.id())

            context_info += f"- {layer.name()} (ID: {layer.id()}): {layer_type} (CRS: {layer.crs().authid()})\n"

        if not user_prompt:
            self.textEdit_response.setPlainText("Please enter a valid prompt.")
            return
        
        available_algorithms = self.fetch_available_algorithms()

        algorithms_info = "## Available Algorithms:\n"
        for alg in available_algorithms:
            algorithms_info += f"- {alg['provider']}: {alg['name']} --> {alg['displayName']}\n"

        # Updated Prompt
        full_prompt = f"""
            {context_info}

            {algorithms_info}

            ## Task:
            {user_prompt}

            ## Instructions:
            - Generate a Python script that runs **directly** in the QGIS Python console.
            - Use `processing.run("native:xyz", {{params}})` for processing tools.
            - Ensure outputs are stored in `QgsProject.instance()`.
            - Do **not** use `iface.activeLayer()` unless necessary.
            - When referencing layers in parameters:
                - Use the `layer.id()` in the `LAYERS` parameter.
                - If the layer is a file-based vector, use its `source()` path.
            - Format the response as a Python **code block** with correct indentation.

            ## Example Format:
            ```python
            import processing

            layer1_id = "{layer_ids[0]}"  # First layer ID
            layer2_id = "{layer_ids[1]}"  # Second layer ID

            result = processing.run("native:mergevectorlayers", {{
                'LAYERS': [layer1_id, layer2_id],
                'OUTPUT': "memory:"
            }})

            merged_layer = result['OUTPUT']  # The merged layer in memory
            QgsProject.instance().addMapLayer(merged_layer)  # Add the merged layer to the project
            ```
            WE DONT NEED TO INCLUDE CONTEXT OR FEEDBACK IN THE PROCESSING.RUN COMMAND. we just want the name of the process and the layers.
            Never offer the chance to change the layer id. Every processing commands layer input should just be the layerid we are performing the process on, or the other ones. 
            Ensure this is all formatted within a python code block.
            use the layer ids from the context above and NEVER prompt the user to input the layer id.
            Only attempt to generate code using the algorithms shown in Available Algorithms above. Please do this.
            - Only use one of the algorithms from the list above. Any other algorithm should **not** be used or considered. Please **strictly** follow these instructions.
            """

        try:
            server_url = "http://192.168.1.89:11434/api/generate"
            model = "qwen2.5-coder:7b"

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


    def execute_generated_code(self):
        """Execute the generated Python code from Ollama."""
        generated_code = self.textEdit_response.toPlainText().strip()

        # Clean the code by removing the code block markers
        if generated_code.startswith("```python"):
            generated_code = generated_code[len("```python"):].strip()

        if generated_code.endswith("```"):
            generated_code = generated_code[:-3].strip()

        try:
            # Execute the cleaned Python code
            exec(generated_code)
            self.textEdit_response.append("Code executed successfully.")
        except Exception as e:
            self.textEdit_response.append(f"Error executing code: {str(e)}")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
