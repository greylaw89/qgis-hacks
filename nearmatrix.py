from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingFeatureSource
from qgis.core import QgsVectorLayer, QgsVectorLayerFeatureSource
from qgis.core import QgsFields, QgsField, QgsFeature, QgsWkbTypes
from PyQt5.QtCore import QVariant
import processing


class NearMatrix(QgsProcessingAlgorithm):
    

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource('input', 'Input Layer', types=[QgsProcessing.TypeVectorAnyGeometry])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource('near', 'Near Layer', types=[QgsProcessing.TypeVectorAnyGeometry])
        )
        self.addParameter(
            QgsProcessingParameterField('inputfield', 'Input Field', type=QgsProcessingParameterField.Any, parentLayerParameterName='input')
        )
        self.addParameter(
            QgsProcessingParameterField('nearfield', 'Near Field', type=QgsProcessingParameterField.Any, parentLayerParameterName='near')
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink('output', 'Near Matrix', type=QgsProcessing.TypeFile)
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(0, model_feedback)
        results = {}
        outputs = {}
        
        input = self.parameterAsSource(parameters, "input", context)
        input_field = self.parameterAsString(parameters, "inputfield", context)
        near = self.parameterAsSource(parameters, "near", context)
        near_field = self.parameterAsString(parameters, "nearfield", context)
        
        if input.sourceCrs() != near.sourceCrs():
            result = processing.run("native:reprojectlayer", {"INPUT": parameters["near"], "TARGET_CRS": input.sourceCrs(), "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT}, context = context, feedback = model_feedback, is_child_algorithm = True)
            near = context.takeResultLayer(result["OUTPUT"])
        
        output_fields = QgsFields()
        output_fields.append(input.fields().field(input_field))
        near_out_field = near.fields().field(near_field)
        
        if input_field == near_field:
            near_out_field.setName(near_field + "_")
        
        output_fields.append(near_out_field)
        output_fields.append(QgsField("distance", QVariant.Double, "double"))
        
        output_geom_type = QgsWkbTypes.LineString
        
        output = self.parameterAsSink(parameters, "output", context, output_fields, output_geom_type, input.sourceCrs())[0]
        
        input_features = [i for i in input.getFeatures()]
        near_features = [i for i in near.getFeatures()]
        
        input_idx = 0
        input_count = len(input_features)
        near_count = len(near_features)
        
        feedback.pushDebugInfo(f"Input Count: {input_count}, Near Count: {near_count}")
        
        for input_feature in input_features:
            input_id = input_feature.attribute(input_field)
            input_shape = input_feature.geometry()
            
            for near_feature in near_features:
                near_id = near_feature.attribute(near_field)
                near_shape = near_feature.geometry()
                distance = input_shape.distance(near_shape)
                line = input_shape.shortestLine(near_shape)
                
                result = QgsFeature()
                result.setFields(output_fields)
                result.setAttribute(0, input_id)
                result.setAttribute(1, near_id)
                result.setAttribute(2, distance)
                result.setGeometry(line)
                output.addFeature(result)
                
                continue 
                
            input_idx += 1
            progress = (input_idx / input_count) * 100
            feedback.setProgress(progress)
            
            if feedback.isCanceled():
                break
            continue 

        return results

    def name(self):
        return 'nearmatrix'

    def displayName(self):
        return 'Near Matrix'

    def group(self):
        return 'QGIS Hacks'

    def groupId(self):
        return 'klaw-qgishacks'

    def createInstance(self):
        return NearMatrix()
