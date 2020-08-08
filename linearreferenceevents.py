 # -*- coding: utf-8 -*- 

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
from math import sqrt
from PyQt5.QtCore import QVariant
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterMultipleLayers,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterBoolean,
                       QgsProcessingUtils,
                       QgsFields,
                       QgsField,
                       QgsWkbTypes,
                       QgsUnitTypes,
                       QgsFeature,
                       QgsGeometry,
                       QgsMultiPoint,
                       QgsPoint,
                       QgsPointXY)
import processing


def measure_along_line(line_vertices, vertex_idx_before, point_on_line):
    """
    """
    distance = 0

    # Handles all vertices PRIOR to vertex before point_on_line. Reduction of one is to handle lookahead process. At loop termination, the v2 value will have the vertex before the point.
    vertex_idx = 0
    while vertex_idx < vertex_idx_before - 1:
        v1 = line_vertices[vertex_idx]
        v2 = line_vertices[vertex_idx + 1]
        
        vxd = v1.x() - v2.x()
        vyd = v1.y() - v2.y()
        
        distance += sqrt(vxd ** 2 + vyd ** 2)
        vertex_idx += 1
        continue
    
    # Use case if measure is between vertices 0 & 1 (first segment)
    if vertex_idx_before < 2:
        v2 = line_vertices[0]
    
    #Final distance addition from last vertex before point_on_line to point_on_line
    vxd = v2.x() - point_on_line.x()
    vyd = v2.y() - point_on_line.y()
    distance += sqrt(vxd ** 2 + vyd ** 2)
    
    return distance
    
def distance_fancy_str(distance, unit, modulo = 100):
    first = int(distance / modulo)
    second = round(distance % modulo)
    return f"{first}+{second}"

def min_max_sort(feature):
    distance_on_line = feature.attributes()[5]
    return distance_on_line


class LinearReferenceEventsAlgorithm(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.
    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.
    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = 'INPUT'
    EVENTS = 'EVENTS'
    EPSILON = 'EPSILON'
    CONSOLIDATE = 'CONSOLIDATE'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return LinearReferenceEventsAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'linearreferenceevents'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Linear Reference Events')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('klaw-processing')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'klaw-processing'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("Example algorithm short description")

    def flags(self):
        return QgsProcessingAlgorithm.FlagNoThreading

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input Alignment'),
                [QgsProcessing.TypeVectorLine]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.EPSILON,
                self.tr("Epsilon Distance"),
                QgsProcessingParameterNumber.Double,
                -1
            )
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CONSOLIDATE,
                self.tr("Consolidate Records"),
                True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.EVENTS,
                self.tr("Event Points")
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output Record Table')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        alignment = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )
        
        if alignment is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        
        alignment_count = alignment.featureCount()
        alignment_wkb = alignment.wkbType()
        alignment_crs = alignment.sourceCrs()
        alignment_units = QgsUnitTypes.toString(alignment_crs.mapUnits())
        
        feedback.pushInfo('CRS is {0}, Units are {1}'.format(alignment_crs.authid(), alignment_units))
        
        if alignment_count != 1:
            raise QgsProcessingException("Alignment has more than one feature. Only one singlepart feature is allowed.")
        if QgsWkbTypes.isMultiType(alignment_wkb):
            raise QgsProcessingException("Alignment has multipart geometry. Convert LAYER to single parts.")
        if alignment_crs.isGeographic():
            raise QgsProcessingException("Alignment has geographic coordinate system. Convert to planar system with units in feet.")
        if alignment_units != "feet":
            raise QgsProcessingException("Alignment has projection in other units than feet. Convert to planar system with units in feet.")
        
        alignment_feature = alignment.getFeatures().__next__()
        alignment_geometry = alignment_feature.geometry()
        alignment_shape = alignment_geometry.get()
        alignment_vertices = [i for i in alignment_shape.vertices()]
        
        epsilon = self.parameterAsDouble(
            parameters,
            self.EPSILON,
            context
        )
        
        consolidate = self.parameterAsBool(
            parameters,
            self.CONSOLIDATE,
            context
        )
        
        event_layers = self.parameterAsLayerList(
            parameters,
            self.EVENTS,
            context
        )
        
        if event_layers is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.EVENTS))
        
        total_event_features = 0
        mod_event_layers = []
        
        for event_layer in event_layers:
            event_name = event_layer.name()
            event_count = event_layer.featureCount()
            event_wkb = event_layer.wkbType()
            event_geom = QgsWkbTypes.geometryType(event_wkb)
            event_multi = QgsWkbTypes.isMultiType(event_wkb)
            event_crs = event_layer.sourceCrs()
            event_units = QgsUnitTypes.toString(event_crs.mapUnits())
            
            if event_count < 1:
                feedback.pushInfo("Event Layer {0} is empty. Skipping...".format(event_name))
                continue
            
            if event_crs != alignment_crs:
                raise QgsProcessingException("Alignment CRS mismatch with Event Layer {0} CRS!".format(event_name))
            
            if event_multi:
                event_layer = processing.run("native:multiparttosingleparts", {
                    "INPUT": event_layer,
                    "OUTPUT": "memory:"
                }, context = context, feedback = feedback)["OUTPUT"]
            
            if event_geom > 1:
                if False:
                    event_layer = processing.run("qgis:densifygeometriesgivenaninterval", {
                        "INPUT": event_layer,
                        "INTERVAL": 10,
                        "OUTPUT": "memory:"
                    }, context = context, feedback = feedback)["OUTPUT"]
                
                event_layer = processing.run("native:extractvertices", {
                    "INPUT": event_layer,
                    "OUTPUT": "memory:"
                }, context = context, feedback = feedback)["OUTPUT"]
            
            event_layer.setName(event_name)
            total_event_features += event_count
            mod_event_layers.append(event_layer)
            
            continue 

        OUTPUTFIELDS = QgsFields()
        OUTPUTFIELDS.append(QgsField("fid", QVariant.LongLong, "int"))
        OUTPUTFIELDS.append(QgsField("event_id", QVariant.String, "string", 255))
        OUTPUTFIELDS.append(QgsField("event_layer", QVariant.String, "string", 255))
        OUTPUTFIELDS.append(QgsField("event_comment", QVariant.String, "string"))
        OUTPUTFIELDS.append(QgsField("distance_away", QVariant.Double, "double"))
        OUTPUTFIELDS.append(QgsField("distance_line", QVariant.Double, "double"))
        OUTPUTFIELDS.append(QgsField("distance_line_str", QVariant.String, "string", 255))
        OUTPUTFIELDS.append(QgsField("side_of_line", QVariant.String, "string", 255))
        OUTPUTFIELDS.append(QgsField("line_x", QVariant.Double, "double"))
        OUTPUTFIELDS.append(QgsField("line_y", QVariant.Double, "double"))
        OUTPUTFIELDS.append(QgsField("event_type", QVariant.String, "string", 255))
        
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            OUTPUTFIELDS,
            QgsWkbTypes.MultiPoint,
            alignment_crs
        )
        
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        
        feedback.setProgress(0)
        
        output_fid = 1
        for event_layer in mod_event_layers:
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break
            
            event_name = event_layer.name()
            event_fields = event_layer.fields()
            event_idx = event_fields.indexOf("GUID")
            comment_idx = event_fields.indexOf("comment")
            events = event_layer.getFeatures()
            
            for event in events:
                egeom = event.geometry()
                eshape = egeom.constGet()
                epoint = QgsPointXY(eshape.x(), eshape.y())
                epoint = QgsPoint(epoint)
                
                if event_idx > -1:
                    eid = event.attributes()[event_idx]
                else:
                    eid = "-"
                    
                if comment_idx > -1:
                    comment = event.attributes()[comment_idx]
                else:
                    comment = ""
                
                results = alignment_shape.closestSegment(eshape)
                distance_away = sqrt(results[0])
                point_on_line = results[1]
                vertex_idx_after = results[2].vertex
                side_of_line = results[3]
                
                if distance_away > epsilon and epsilon != -1:
                    continue
                
                if side_of_line == -1:
                    side_of_line = "Left"
                elif side_of_line == 1:
                    side_of_line = "Right"
                else:
                    side_of_line = "Unknown / On Line"
                
                distance_on_line = measure_along_line(alignment_vertices, vertex_idx_after - 1, point_on_line)
                point_on_line = QgsPointXY(point_on_line.x(), point_on_line.y())
                point_on_line = QgsPoint(point_on_line)
                
                record = QgsFeature()
                record.setFields(OUTPUTFIELDS)
                record.setAttribute(0, output_fid)
                record.setAttribute(1, str(eid))
                record.setAttribute(2, event_name)
                record.setAttribute(3, comment)
                record.setAttribute(4, distance_away)
                record.setAttribute(5, distance_on_line)
                record.setAttribute(6, distance_fancy_str(distance_on_line, alignment_units))
                record.setAttribute(7, side_of_line)
                record.setAttribute(8, point_on_line.x())
                record.setAttribute(9, point_on_line.y())
                record.setAttribute(10, "Unitary")
                
                if output_fid % 1000 == 0 and False:
                    feedback.pushDebugInfo(str(repr(epoint) + "  " + repr(point_on_line)))
                
                
                record_shape = QgsMultiPoint()
                record_shape.addGeometry(epoint)
                record_shape.addGeometry(point_on_line)
                record_geometry = QgsGeometry(record_shape)
                
                record.setGeometry(record_geometry)
                
                if output_fid % 1000 == 0 and True:
                    feedback.pushDebugInfo("Record Successfully Generated!")
                
                sink.addFeature(record)
                
                output_fid += 1
                feedback.setProgress(int(output_fid / total_event_features))
                
                continue
            sink.flushBuffer()
            continue
            
        sink = QgsProcessingUtils.mapLayerFromString(dest_id, context)
        
        if consolidate:
            output_unique = list(sink.uniqueValues(1))
            for unique in output_unique:
                if unique == "-":
                    continue
                
                sink.selectByExpression(""""event_id" = '{0}'""".format(unique))
                
                unique_count = sink.selectedFeatureCount()
                if unique_count == 1:
                    continue
                
                sink.startEditing()
                feedback.pushDebugInfo("Clearing middle points for {0}".format(unique))
                
                features = [i for i in sink.getSelectedFeatures()]
                features.sort(key = min_max_sort)
                min_fid = features[0].attributes()[0]
                max_fid = features[-1].attributes()[0]
                dispose_fids = [str(i.attributes()[0]) for i in features[1:-1]]
                dispose_fids_sql = '(' + ",".join(dispose_fids) + ')'
                
                sink.removeSelection()
                sink.selectByExpression(""""fid" IN {0}""".format(dispose_fids_sql))
                count = sink.deleteSelectedFeatures()
                sink.removeSelection()
                
                sink.changeAttributeValue(min_fid, 10, "Start")
                sink.changeAttributeValue(max_fid, 10, "End")
                
                feedback.pushDebugInfo("Features deleted: {0}".format(str(count)))
                sink.commitChanges()
                
                continue

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}
