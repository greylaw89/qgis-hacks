# This is a git commit comment
from PyQt5.QtCore import QVariant 
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingFeatureSource
from qgis.core import QgsVectorLayer, QgsVectorLayerFeatureSource
from qgis.core import QgsFields, QgsField, QgsFeature, QgsWkbTypes
import processing


class NearMatrixAlgorithm(QgsProcessingAlgorithm):
    
    INPUT = "INPUT"
    NEAR = "NEAR"
    INPUTFIELD = "INPUTFIELD"
    NEARFIELD = "NEARFIELD"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.INPUT, 'Input Layer', types=[QgsProcessing.TypeVectorAnyGeometry])
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.NEAR, 'Near Layer', types=[QgsProcessing.TypeVectorAnyGeometry])
        )
        self.addParameter(
            QgsProcessingParameterField(self.INPUTFIELD, 'Input Field', type=QgsProcessingParameterField.Any, parentLayerParameterName=self.INPUT)
        )
        self.addParameter(
            QgsProcessingParameterField(self.NEARFIELD, 'Near Field', type=QgsProcessingParameterField.Any, parentLayerParameterName=self.NEAR)
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, 'Near Matrix', type=QgsProcessing.TypeFile)
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(1, feedback)
        results = {}
        outputs = {}
        
        input = self.parameterAsSource(parameters, self.INPUT, context)
        input_field = self.parameterAsString(parameters, self.INPUTFIELD, context)
        near = self.parameterAsSource(parameters, self.NEAR, context)
        near_field = self.parameterAsString(parameters, self.NEARFIELD, context)
        
        if input.sourceCrs() != near.sourceCrs():
            result = processing.run("native:reprojectlayer", {"INPUT": parameters[self.NEAR], "TARGET_CRS": input.sourceCrs(), "OUTPUT": "memory:"}, context = context, feedback = feedback, is_child_algorithm = True)
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
        return NearMatrixAlgorithm()