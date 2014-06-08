# -*- coding: utf-8 -*-


"""
*****************************************************************************
    functions_for_matching_script.py
    ---------------------
    Date                 : June 2014
    Copyright            : (C) 2014 by Julian Will
    Email                : julianwill88 at web dot de
*****************************************************************************
*                                                                           *
*   This program is free software; you can redistribute it and/or modify    *
*   it under the terms of the GNU General Public License as published by    *
*   the Free Software Foundation; either version 2 of the License, or       *
*   (at your option) any later version.                                     *
*                                                                           *
*   It is distributed in the hope that it will be useful, but WITHOUT ANY   *
*   WARRANTY; without even the implied warranty of MERCHANTABILITY or       *
*   FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License    *
*   for more details.                                                       *
*                                                                           *
*   For a copy of the GNU General Public License see                        *
*   "http://www.gnu.org/licenses/gpl-3.0.en.html".                          *
*                                                                           *
*   The latest source for this software can be accessed at                  *
*   "https://github.com/JulianWill/Linear_Feature_matching/"                *
*                                                                           *
*****************************************************************************
*                                                                           *
*   This script contain three functions used by                             *
*   Linear_feature_matching.py                                              *
*                                                                           *
*****************************************************************************
"""

def split_into_segments(input_file, output_file):
    'function to split a line vector into its segments. The part between two vertexes. Normalized direction of each segment is calculates.Result is writen to a new shapefile'
    # import moduls
    from qgis.core import*
    from PyQt4.QtCore import *
    import math
    from processing.core.VectorWriter import VectorWriter
    
    # open input file as QGIS layer and assigne to variable
    layer=QgsVectorLayer(input_file, "feature_layer", "ogr")
    # fetch data provider
    provider=layer.dataProvider()
    # get attribute fields of layer
    fields = layer.pendingFields().toList()
    # add new attribute fields to store, feature id, direction, match id, match feature Id 
    fields.append(QgsField("featureId", QVariant.Int))
    fields.append(QgsField("direction", QVariant.Double))
    fields.append(QgsField("matchId", QVariant.String))
    fields.append(QgsField("matchFeatId", QVariant.Int))

    # define output location 
    segment=output_file
    # define feature writer
    writer = VectorWriter(segment, None, fields, provider.geometryType(), layer.crs())
    # define output feature
    outFeat = QgsFeature()

    # for each feature in layer
    features=layer.getFeatures()
    for feature in features:
        geom= feature.geometry()
        xy=geom.asPolyline()
        # for each point pair in feature
        for x in range(0, len(xy)-1):
            line_start=xy[x]
            line_end=xy[x+1]
            # define geometry of ouput feature (a new segment)
            outFeat.setGeometry(QgsGeometry.fromPolyline([line_start,line_end]))
            # copy attribute information form orginal feature
            attri = feature.attributes()
            # add feature id information
            attri.append(int(feature["id_clip"]))
            # add direction information
            directionlist=[]
            directionlist.append(line_start.azimuth(line_end))
            directionlist.append(line_end.azimuth(line_start))
            direction=directionlist[[abs(e) for e in directionlist].index(min([abs(e) for e in directionlist]))]
            attri.append(float(direction))
            # assigne attribute information to output feature
            outFeat.setAttributes(attri)
            # write output feature to segment shapefile
            writer.addFeature(outFeat)
    del writer
    return

def add_field(Dir,name,type):
    'function which add a field of name  with of type(Integer=0,Double=1,String=2) to input layer(dirctroy path) if field not already exits'
    from qgis.core import*
    from PyQt4.QtCore import *
    type_dic={0:QVariant.Int,1:QVariant.Double,2:QVariant.String}
    Layer=QgsVectorLayer(Dir, "layer", "ogr")
    if not name in [f.name() for f in Layer.pendingFields().toList()]:
        fieldtype=type_dic[type]
        Layer.startEditing()
        Layer.dataProvider().addAttributes([QgsField(name, fieldtype)])
        Layer.updateFields()
        Layer.commitChanges()
    return

def unique_ID(Dir,name,ID_counter):
    'function which add a field of name a unique ID for complete study area'
    from qgis.core import*
    from PyQt4.QtCore import *
    Layer=QgsVectorLayer(Dir, "layer", "ogr")
    Layer.startEditing()
    index=[f.name() for f in Layer.pendingFields().toList()].index(name)
    Features=Layer.getFeatures()
    for f in Features:
            Layer.changeAttributeValue(f.id(),index,f.id()+ID_counter)
    Layer.commitChanges()
    return f.id()+ID_counter+1

