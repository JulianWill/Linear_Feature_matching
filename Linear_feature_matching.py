# -*- coding: utf-8 -*-
from __future__ import division

"""
*****************************************************************************
   	Linera_feature_matching.py
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
*   																		*
*   It is distributed in the hope that it will be useful, but WITHOUT ANY   *
*   WARRANTY; without even the implied warranty of MERCHANTABILITY or       *
*   FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License    *
*   for more details.                                                       *
* 																			*
*   For a copy of the GNU General Public License see						*
*   "http://www.gnu.org/licenses/gpl-3.0.en.html".       		      	    *
* 																			*
*   The latest source for this software can be accessed at                  *
*   "https://github.com/JulianWill/Linear_Feature_matching/"				*
*                                                          	                *
*****************************************************************************
*																		    *
*   This script matches two linear feature data sets. Script requires	    *
*   access to the config_file_matching.ini and 							    *
*   functions_for_matching_script.py 									    *
*	For a more detail description of this matching routine see 			    *
*	readme.txt       													    *
*																		    *
*****************************************************************************
"""

# Load packages
import processing
from qgis.core import*
from PyQt4.QtCore import *

import os
import math
from collections import defaultdict
import json
import datetime
import time
import itertools
import glob
import sys
import codecs
from ConfigParser import SafeConfigParser
import shutil

from shapely.geometry import LineString
from nltk import metrics

############################################################################
# load config file:
parser = SafeConfigParser()
parser.read('E:/Master/11_masteruppasats/999/config_file_matching_2.ini')							# define path of congif file

# define path of functiont script
Dir_func=parser.get('script_path', 'Dir_func')  
sys.path.insert(0,Dir_func)
from functions_for_matching_script import split_into_segments,add_field,unique_ID

# define input and output file directories
#******************************************
Dir_OSM_roads=parser.get('input_files', 'Dir_OSM_roads')  								# shapefile with OSM roads
Dir_LM_roads=parser.get('input_files', 'Dir_LM_roads')									# shapefile with LM roads
Dir_SA=parser.get('input_files', 'Dir_SA')	
Output_location=parser.get('input_files', 'Output_location')							# directory where output directories should be created
Input_location=parser.get('input_files', 'Input_location')	
Temp_location=parser.get('input_files', 'Temp_location')	

# create output file directories
Dir_OUT_Feat=Output_location+"features/"											# output directory for all feature layers
if not os.path.exists(Dir_OUT_Feat):												# if directory not exist
	os.makedirs(Dir_OUT_Feat)														# create directory
Dir_OUT_Simp_Feat=Output_location+"simplified/features/"							# output directory for all segment layers
if not os.path.exists(Dir_OUT_Simp_Feat):											# if directory not exist
	os.makedirs(Dir_OUT_Simp_Feat)													# create directory
Dir_OUT_Simp_Seg=Output_location+"simplified/segments/"								# output directory for all segment layers
if not os.path.exists(Dir_OUT_Simp_Seg):											# if directory not exist
	os.makedirs(Dir_OUT_Simp_Seg)													# create directory			
Dir_results=Output_location+"text_files/"											# output directory to store QA results as text files
if not os.path.exists(Dir_results):													# if directory not exist
	os.makedirs(Dir_results)														# create directory
Dir_tiles=Input_location+"tiles/"													# directory to store tile files of study area
if not os.path.exists(Dir_tiles):													# if directory not exist
	os.makedirs(Dir_tiles)															# create directory
Dir_temp=Temp_location																# directory to store tile files of study area
if not os.path.exists(Dir_temp):													# if directory not exist
	os.makedirs(Dir_temp)															# create directory

SA_temp_buffer=Dir_temp+"temp_buffer.shp"											# path to store the buffer around a study area tile

# create tile files
#**************************************************************************

SA=QgsVectorLayer(Dir_SA, "study_area", "ogr")
Areas=SA.getFeatures()
area_counter=1
ID_counter=0
for area in Areas:
	processing.runalg("qgis:creategrid",1000,1000,area.geometry().boundingBox().width(),area.geometry().boundingBox().height(),area.geometry().boundingBox().center()[0],area.geometry().boundingBox().center()[1],1,SA.crs().authid(),Dir_temp+"temp"+str(area.id())+".shp")
	tmp=QgsVectorLayer(Dir_temp+"temp"+str(area.id())+".shp", "tmp", "ogr")
	tiles_intersect=[]
	for tile in tmp.getFeatures():
		if tile.geometry().intersects(area.geometry())==True:
			tiles_intersect.append(tile.id())
	tmp.setSelectedFeatures([f for f in tiles_intersect])
	
	QgsVectorFileWriter.writeAsVectorFormat(tmp, Dir_tiles+"SA_grid_"+str(area_counter)+".shp", "latin1", SA.crs(),"ESRI Shapefile",True)
	add_field(Dir_tiles+"SA_grid_"+str(area_counter)+".shp","ID",0)
	add_field(Dir_tiles+"SA_grid_"+str(area_counter)+".shp","LM_match",1)
	add_field(Dir_tiles+"SA_grid_"+str(area_counter)+".shp","OSM_match",1)
	ID_counter=unique_ID(Dir_tiles+"SA_grid_"+str(area_counter)+".shp","ID",ID_counter)
	area_counter+=1

# define attribute names:
attri_id_tile="ID"
attri_OSM_match_tile="OSM_match"
attri_LM_match_tile="LM_match"

# define input variables:
#**************************************************************************

# define encoding of dataset:
# encoding of LM data
encoding_LM=parser.get('encoding_information', 'encoding_LM')
# encoding of OSM data
encoding_OSM=parser.get('encoding_information', 'encoding_OSM')

# define attribute names:
# for LM data
# column name of road name attribute of LM data:
attri_name_LM=parser.get('LM_attribute_names', 'attri_name_LM')
# column name of road type attribute of LM data:
attri_roadtype_LM=parser.get('LM_attribute_names', 'attri_roadtype_LM')

#for OSM data
# column name of road name attribute of OSM data:
attri_name_OSM=parser.get('OSM_attribute_names', 'attri_name_OSM')

# create required attribute columns for LM and OSM dataset:
# LM data
# attribute id_clip, stores for each feature a individiual id
add_field(Dir_LM_roads,"id_clip",0)
attri_id_clip_LM="id_clip"
unique_ID(Dir_LM_roads,"id_clip",0)
# attribute OSM_match, to store Ids of matching OSM features
add_field(Dir_LM_roads,"OSM_match",2)
attri_match_LM="OSM_match"
# OSM data
# attribute id_clip, stores for each feature a individiual id
add_field(Dir_OSM_roads,"id_clip",0)
attri_id_clip_OSM="id_clip"
unique_ID(Dir_OSM_roads,"id_clip",0)
# attribute OSM_match, to store Ids of matching LM features
add_field(Dir_OSM_roads,"LM_match",2)
attri_match_OSM="LM_match"


# get all unique road type of LM from config file and create dictionary with their roadwidth:
with codecs.open('E:/Master/11_masteruppasats/999/config_file.ini', 'r', encoding='utf-8') as f:
    parser.readfp(f)
LM_road_type=parser.get('LM_road_type', '1')  	
LM_road_type=[t.strip() for t in LM_road_type.split(',')]
roadtype_dic={}
for t in range(0,len(LM_road_type),2):
	roadtype_dic[LM_road_type[t]]=int(LM_road_type[t+1])

# variable used in algorithm
# GPS accuracy: (used in step 1 and 6)
GPS_accuracy=10
# Douglas Peuker threshold: (used before step 1)
DP_threshold=1
# buffersize for tile layer:
BS_tiles=50
# name similarity threshold step 4:
NS_threshold_S4=0.65
# name similarity threshold step 6:
NS_threshold_S6=0.75

#*****************************************************************************
# varibles to store statistic information
# execution time per tile
time_per_tile=defaultdict(list)
# for LM match percentag per step
total_match_length_feat_LM=0							# save total match length
match_length_step_LM={1:0,2:0,3:0,4:0,5:0,6:0,7:0}		# save match length of each step

# for OSM match percentag per step
total_match_length_feat_OSM=0							# save OSM total match length
match_length_step_OSM={1:0,2:0,3:0,4:0,5:0,6:0,7:0}		# save OSM match length of each step

# for complete study area
total_length_LM_SA=0
total_length_OSM_SA=0
total_match_length_LM_SA=0
total_match_length_OSM_SA=0

#***************************************************************************
# Algorithm starts 
#***************************************************************************
print datetime.datetime.now().time()
time_start=time.time()
tile_files = glob.iglob(Dir_tiles+"*.shp")					# fetch all shapefiles paths which are in tile directory

# for all tiles
###########################################################################
for tile_dir in tile_files:									# for file in directory
	time_start_tile=time.time()
	# load Tile road layer
	Tile_layer=QgsVectorLayer(tile_dir, "Tile_layer", "ogr")					# load Tile road layer
	
	# get attribute colum positions
	Tile_OSMmatch_pos=Tile_layer.fieldNameIndex(attri_OSM_match_tile)			# position of attribute field "OSM_match" of Tile layer
	Tile_LMmatch_pos=Tile_layer.fieldNameIndex(attri_LM_match_tile)				# position of attribute field "LM_match" of Tile layer
	
	for Tile in Tile_layer.getFeatures():
		# select Tile and write to shapefile
		Tile_layer.setSelectedFeatures([Tile.id()])
		QgsVectorFileWriter.writeAsVectorFormat(Tile_layer, Dir_temp+"tile"+str(Tile["ID"])+".shp", "latin1", None,"ESRI Shapefile",True)
		# clip OSM and LM files to buffered tile
		# create 50 meter buffer around tile
		processing.runalg("qgis:fixeddistancebuffer", Dir_temp+"tile"+str(Tile["ID"])+".shp", BS_tiles, 5, True, SA_temp_buffer)	# 50 buffer around Tile, next iteration overwrites the shapefile
		# clip LM roads file to buffer extent and store
		processing.runalg("qgis:clip",Dir_LM_roads,SA_temp_buffer,Dir_OUT_Feat+"LM_Feat_"+str(Tile["ID"])+".shp")
		# clip OSM road file to buffer extent and store
		processing.runalg("qgis:clip",Dir_OSM_roads,SA_temp_buffer,Dir_OUT_Feat+"OSM_Feat_"+str(Tile["ID"])+".shp")

		# simplify feature layers (Douglas-Peucker)
		# simplify LM features
		processing.runalg("qgis:simplifygeometries",Dir_OUT_Feat+"LM_Feat_"+str(Tile["ID"])+".shp",DP_threshold,Dir_OUT_Simp_Feat+"LM_Feat_"+str(Tile["ID"])+".shp")
		# simplify OSM feature
		processing.runalg("qgis:simplifygeometries",Dir_OUT_Feat+"OSM_Feat_"+str(Tile["ID"])+".shp",DP_threshold,Dir_OUT_Simp_Feat+"OSM_Feat_"+str(Tile["ID"])+".shp")

		# convert clipped OSM and LM datasets from features to segments
		# OSM data
		split_into_segments(Dir_OUT_Simp_Feat+"OSM_Feat_"+str(Tile["ID"])+".shp",Dir_OUT_Simp_Seg+"OSM_Seg_"+str(Tile["ID"])+".shp")
		# LM file 
		split_into_segments(Dir_OUT_Simp_Feat+"LM_Feat_"+str(Tile["ID"])+".shp",Dir_OUT_Simp_Seg+"LM_Seg_"+str(Tile["ID"])+".shp")
		print "segmentation finished"

		# match LM and OSM datasets for tile
		#***********************************

		# define file directories
		Dir_OSM=Dir_OUT_Simp_Feat+"OSM_Feat_"+str(Tile["ID"])+".shp"
		Dir_OSM_Seg=Dir_OUT_Simp_Seg+"OSM_Seg_"+str(Tile["ID"])+".shp"
		Dir_LM=Dir_OUT_Simp_Feat+"LM_Feat_"+str(Tile["ID"])+".shp"
		Dir_LM_Seg=Dir_OUT_Simp_Seg+"LM_Seg_"+str(Tile["ID"])+".shp"

		# load datasets
		OSM_feature_layer=QgsVectorLayer(Dir_OSM, "OSM_features", "ogr")
		LM_feature_layer=QgsVectorLayer(Dir_LM, "LM_features", "ogr")
		OSM_segment_layer=QgsVectorLayer(Dir_OSM_Seg, "OSM_segments", "ogr")
		LM_segment_layer=QgsVectorLayer(Dir_LM_Seg, "LM_segments", "ogr")

		# get attribute colum positions
		LMSeg_matchID_pos=LM_segment_layer.fieldNameIndex("matchId")				# position of attribute field "mathcId" of LM segment layer
		OSMSeg_matchID_pos=OSM_segment_layer.fieldNameIndex("matchId")			# position of attribute field "mathcId" of OSM segment layer

		LMSeg_matchFeatId_pos=LM_segment_layer.fieldNameIndex("matchFeatI")		# position of attribute field "matchFeatI" of LM segment layer
		OSMSeg_matchFeatId_pos=OSM_segment_layer.fieldNameIndex("matchFeatI")	# position of attribute field "matchFeatI" of OSM segment layer

		LMFeat_OSMmatch_pos=LM_feature_layer.fieldNameIndex("OSM_match")		# position of attribute field "OSM_match" of LM feature layer
		OSMFeat_LMmatch_pos=OSM_feature_layer.fieldNameIndex("LM_match")		# position of attribute field "LM_match" of OSM feature layer

		# Calculate segment candidate list
		###################################

		LM_segments=LM_segment_layer.getFeatures() 						# make LM layer iterable

		counter=0 														# create counter
		osm_cc=[]														# create list to count how often a OSM segment is used as candidate
		osm_removed_cc=[]                       						# create list to count how often a OSM candidate is removed from candidate list
		candidatelist=[]
		for LMsegment in LM_segments:									# for each LM segment
			candidatelist.append([LMsegment.id()])						# update candidate list in fowling iterations 
			roadtype=LMsegment[attri_roadtype_LM]								# calculate road width depending on street type
			if roadtype in roadtype_dic:								# find roadtype of LM segment in dictionary
			 	roadwidth=roadtype_dic[roadtype]							# retrive roadtype width from corresponding roadtype key
			else:														# if road type is not defined
				print LMsegment[attri_roadtype_LM]								# print roadtype 
				#sys.exit("roadtype not defined")							# stop script and rais error message
			buffersize=2*GPS_accuracy+roadwidth/2 								# calculate buffer size
			Buffer=LMsegment.geometry().buffer(buffersize,100)			# create buffer depending on road width 
			# add OSM segments as candidates when within buffer
			OSM_segments=OSM_segment_layer.getFeatures() 				# make OSM layer iterable
			for OSMsegment in OSM_segments:								# for each OSM segments
				if OSMsegment.geometry().within(Buffer) == True:		# check if it intersect with buffer
					candidatelist[counter].append(OSMsegment.id())		# if yes, assign segment id to list of LM candidate
					osm_cc.append(OSMsegment.id())						# add OSM segment to OSM candidate counter
			
			# check if candidates are with a angular tolerance 
			angualar_tolerance=(180/math.pi)*math.atan(GPS_accuracy/(LMsegment.geometry().length()/2)) 		# calculate angular tolerance for LM segment
			iterat_list=list(candidatelist[counter])									# subset of candidate list, used in iteration over all OSM segments for active LM segment 
			c_counter=0 																# counter for iteration over iter_list			 				
			sum_del_candidates=0 														# counter to keep track of number of deleted OSM candidates
			for x in iterat_list:														# for each candidate for that LM segment
				if c_counter!=0:
					request = QgsFeatureRequest().setFilterFid(x)						# create request to select first OSM candidate
					candidate = OSM_segment_layer.getFeatures(request).next()			# select OSM candidate
					# calculate angular difference between the two segments
					if LMsegment["direction"]<0 and candidate["direction"]>0:					# if LM segment has negative and candidatie has positive orientation
						angular_diff=(LMsegment["direction"]+90)+(90-candidate["direction"])	
					elif LMsegment["direction"]>0 and candidate["direction"]<0:					# if LM segment has positve and candidatie has negative orientation
						angular_diff=(90-LMsegment["direction"])+(candidate["direction"]+90)
					else:																		# if both orientation have the same sign
						angular_diff=abs(LMsegment["direction"]-candidate["direction"])		
					if angular_diff > angualar_tolerance:								# if difference is greater than tolerance
						del candidatelist[counter][c_counter-sum_del_candidates]		# add OSM candidate to remove list
						osm_removed_cc.append(x)										# add OSM candidate to removed candidate counter list
						sum_del_candidates=sum_del_candidates+1
				c_counter=c_counter+1
			counter= counter+1 											# increase counter by one
		#candidatelist_initial=list(candidatelist)						# create copy of candidatelist
		#print len(candidatelist),"1"
		#print candidatelist

		# Stage 1: find 1:1 matches with length constrain
		#################################################
		OSM_segment_layer.startEditing()								# make OSM segment layer editable
		LM_segment_layer.startEditing()									# make LM segment layer editable
		iterat_list=list(candidatelist)									# create copy of list to use to iterate over
		iterat_counter=0                                                # iteration counter
		sum_del_candidates=0 											# counter to keep track of number of deleted LM candidates
		OSM_match_dic=defaultdict(list)									# create list dictionary to store OSM segments match id's

		for x in iterat_list:											# for each item(LM segment) in iteration list
			if len(x)==2:												# if LM segmment has only one candidate, then
				osm_count=osm_cc.count(x[1])-osm_removed_cc.count(x[1])		# count how often a OSM segment is a candidate
				if osm_count==1:											#if OSM segment is only once a candidate, then
					OSMrequest = QgsFeatureRequest().setFilterFid(x[1])									# create request to select OSM candidate
					OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()						# select OSM candidate
					LMrequest = QgsFeatureRequest().setFilterFid(x[0])									# create request to select LM candidate
					LMcandidate = LM_segment_layer.getFeatures(LMrequest).next()						# select LM candidate
					if 3*LMcandidate.geometry().length()>OSMcandidate.geometry().length():								# if OSM candidate is less than three times the length of the LMcandidate, then
						LM_segment_layer.changeAttributeValue(LMcandidate.id(),LMSeg_matchID_pos,OSMcandidate.id())				# add matching OSM Id to LM segment layer to matchid attribute field
						LM_segment_layer.changeAttributeValue(LMcandidate.id(),LMSeg_matchFeatId_pos,OSMcandidate["featureId"])	# add Id of matchings segments feature to LM segment layer to matchid attribute field
						OSM_match_dic[OSMcandidate.id()].append([LMcandidate.id(),LMcandidate["featureId"],1])					# add LM feature match id as value to key matching OSM segment
						match_length_step_LM[1]+=LMcandidate.geometry().length()													# add feature length to matching length step 1
						del candidatelist[(iterat_counter-sum_del_candidates)]							# delete LM segment from counter 
						sum_del_candidates=sum_del_candidates+1 										# sum_del_candidates plus 1
			iterat_counter=iterat_counter+1 							# iteration counter plus 1

		#candidatelist_1=list(candidatelist)							# create copy of candidatelist
		#print len(candidatelist),"2"
		#print OSM_match_dic

		# Stage 2: find matches depending on exact name attribute
		#########################################################
		iterat_list=list(candidatelist)									# create copy of list to use to iterate over
		iterat_counter=0                                                # iteration counter
		sum_del_candidates=0 											# counter to keep track of number of deleted LM candidates
		for x in iterat_list:
			LMrequest = QgsFeatureRequest().setFilterFid(x[0])							# create request to select LM candidate
			LMcandidate = LM_segment_layer.getFeatures(LMrequest).next()				# select LM candidate
			if LMcandidate[attri_name_LM]==NULL:												# skip if LM segment has no name attribute
				iterat_counter=iterat_counter+1 										# iteration counter plus 1
			else:
				same_name_list=[LMcandidate.id()]											# create same-name-list and add LM segment id to list
		 		for y in range(1,len(x)):													# for each OSM candidate
					OSMrequest = QgsFeatureRequest().setFilterFid(x[y])						# create request to select OSM candidate
		 			OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()			# select OSM candidate
		 			if OSMcandidate[attri_name_OSM]==LMcandidate[attri_name_LM]:							# if LM and OSM segment have same name, then
		 				same_name_list.append(OSMcandidate.id())								# add OSM segment to same-name-list
		 		# check if only one OSM candidate is returned
		 		if len(same_name_list)==2:														# if only one OSM segment has the same name as LM segment
		 			LM_segment_layer.changeAttributeValue(same_name_list[0],LMSeg_matchID_pos,same_name_list[1])				# add matching OSM Id to LM segment layer to matchid attribute field
					OSMrequest = QgsFeatureRequest().setFilterFid(same_name_list[1])											# create request to select OSM candidate
		 			OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()												# select OSM candidate
					LM_segment_layer.changeAttributeValue(same_name_list[0],LMSeg_matchFeatId_pos,OSMcandidate["featureId"])	# add Id of matchings segments feature to LM segment layer to matchid attribute field
					OSM_match_dic[OSMcandidate.id()].append([LMcandidate.id(),LMcandidate["featureId"],2])						# add LM feature match id as value to key matching OSM segment
					del candidatelist[(iterat_counter-sum_del_candidates)]														# delete LM segment from counter 
					sum_del_candidates=sum_del_candidates+1                														# sum_del_candidates plus 1
					match_length_step_LM[2]+=LMcandidate.geometry().length()														# add feature length to matching length step 2
				# if more candidates are returned
				elif len(same_name_list)>2:														# if more candidates with same name
					dist_list=[]																	# creat list to store distance between candidates and LM	
					for t in range(1,len(same_name_list)):											# for all candidates
				 		OSMrequest = QgsFeatureRequest().setFilterFid(same_name_list[t])				# create request to select OSM candidate
		 				OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()					# select OSM candidate
				 		OSM_geom=OSMcandidate.geometry().asPolyline()									# save OSM geometry as Polyline to variable
				 		OSM_P1=OSM_geom[0]																# save first point of OSM segment
				 		OSM_P2=OSM_geom[-1]																# save last point of OSM segment
						LM_geom=LMcandidate.geometry().asPolyline() 									# save LM geometry as Polyline to variable
						LM_P1=LM_geom[0]																# save first point of LM segment
						LM_P2=LM_geom[-1]																# save last point of LM segment
						dist1=LineString([(LM_P1.x(),LM_P1.y()),(OSM_P2.x(),OSM_P2.y())]).length+LineString([(LM_P2.x(),LM_P2.y()),(OSM_P1.x(),OSM_P1.y())]).length
						dist2=LineString([(LM_P1.x(),LM_P1.y()),(OSM_P1.x(),OSM_P1.y())]).length+LineString([(LM_P2.x(),LM_P2.y()),(OSM_P2.x(),OSM_P2.y())]).length
						short_dist=min(dist1,dist2)
						dist_list.append(short_dist)													# add shortest distance between two segments to list
		 	 	 	nearst_candidate=dist_list.index(min(dist_list))+1 								# find closest candidate
				 	LM_segment_layer.changeAttributeValue(same_name_list[0],LMSeg_matchID_pos,same_name_list[nearst_candidate])		# add matching OSM Id to LM segment layer to matchid attribute field
					OSMrequest = QgsFeatureRequest().setFilterFid(same_name_list[nearst_candidate])									# create request to select OSM candidate
		 			OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()													# select OSM candidate
					LM_segment_layer.changeAttributeValue(same_name_list[0],LMSeg_matchFeatId_pos,OSMcandidate["featureId"])		# add Id of matchings segments feature to LM segment layer to matchid attribute field
					OSM_match_dic[OSMcandidate.id()].append([LMcandidate.id(),LMcandidate["featureId"],2])							# add LM feature match id as value to key matching OSM segment
					del candidatelist[(iterat_counter-sum_del_candidates)]															# delete LM segment from counter 
				 	sum_del_candidates=sum_del_candidates+1                															# sum_del_candidates plus 1
				 	match_length_step_LM[2]+=LMcandidate.geometry().length()															# add feature length to matching length step 2
				iterat_counter=iterat_counter+1 							# iteration counter plus 1
		#candidatelist_2=list(candidatelist)							# create copy of candidatelist
		#print len(candidatelist),"3"
		#print candidatelist

		#Stage 3: find matches depending on similar name attribute
		########################################################					
		iterat_list=list(candidatelist)									# create copy of list to use to iterate over
		iterat_counter=0                                                # iteration counter
		sum_del_candidates=0 											# counter to keep track of number of deleted LM candidates
		for x in iterat_list:
			LMrequest = QgsFeatureRequest().setFilterFid(x[0])						# create request to select LM candidate
			LMcandidate = LM_segment_layer.getFeatures(LMrequest).next()			# select LM candidate
			similar_name_value=[]
			similar_charaters=0
			if LMcandidate[attri_name_LM]==NULL:											# do nothing if LM segment has no name attribute
				iterat_counter=iterat_counter+1 									#  only iteration counter plus 1
			else:
				LM_name=LMcandidate[attri_name_LM].encode(encoding_LM)								# LM name to string in latin-1 encoding
		 		LM_name=LM_name.upper()														# make all characters upper letters
		 		for y in range(1,len(x)):													# for each OSM candidate
					OSMrequest = QgsFeatureRequest().setFilterFid(x[y])							# create request to select OSM candidate
		 			OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()				# select OSM candidate
		 			if OSMcandidate[attri_name_OSM]==NULL:
		 				similar_name_value.append(0.0)
		 			else:
			 			OSM_name=OSMcandidate[attri_name_OSM].encode(encoding_OSM)						# OSM name to string in Latin-1 encoding
						OSM_name=OSM_name.upper()												# make all characters upper letters
						max_length=max(len(LM_name),len(OSM_name))								# get maximum length of OSM or LM name
				 		similar_match=1-(metrics.edit_distance(OSM_name, LM_name)/float(max_length))# calculate similar character measurement (levenshtein distance in percentage)
				 		similar_name_value.append(similar_match)								# add value to similar name value list
			 	if similar_name_value:														# if similar name value list is not empty		
				 	highst_value=max(similar_name_value)										# find lowest similar name value
				 	highst_value_index=similar_name_value.index(highst_value)+1 				# find index of highst value
					if highst_value>NS_threshold_S4:														# if highst value is above 0.65
						LM_segment_layer.changeAttributeValue(x[0],LMSeg_matchID_pos,x[highst_value_index])	# add matching OSM Id to LM segment layer to matchid attribute field
						OSMrequest = QgsFeatureRequest().setFilterFid(x[highst_value_index])						# create request to select OSM candidate
				 		OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()								# select OSM candidate
						LM_segment_layer.changeAttributeValue(x[0],LMSeg_matchFeatId_pos,OSMcandidate["featureId"])	# add Id of matchings segments feature to LM segment layer to matchid attribute field
					 	OSM_match_dic[OSMcandidate.id()].append([LMcandidate.id(),LMcandidate["featureId"],3])		# add LM feature match id as value to key matching OSM segment
					 	del candidatelist[iterat_counter-sum_del_candidates]										# delete LM segment from counter 
						sum_del_candidates=sum_del_candidates+1 													# sum_del_candidates plus 1
						match_length_step_LM[3]+=LMcandidate.geometry().length()										# add feature length to matching length step 3
				iterat_counter=iterat_counter+1 							# iteration counter plus 1
		#candidatelist_3=list(candidatelist)							# create copy of candidatelist
		#print len(candidatelist),"4"
		
		# Stage 4: find matches depending on distance to each other
		###########################################################
		iterat_list=list(candidatelist)									# create copy of list to use to iterate over
		iterat_counter=0                                                # iteration counter
		sum_del_candidates=0 											# counter to keep track of number of deleted LM candidates
		for x in iterat_list:
			LMrequest = QgsFeatureRequest().setFilterFid(x[0])						# create request to select LM candidate
			LMcandidate = LM_segment_layer.getFeatures(LMrequest).next()			# select LM candidate
			LM_geom=LMcandidate.geometry().asPolyline() 							# save LM geometry as Polyline to variable
			LM_P1=LM_geom[0]														# save first point of LM segment
			LM_P2=LM_geom[-1]														# sace last point of LM segment
			dist_list=[]
			for y in range(1,len(x)):												# for each OSM candidate
				OSMrequest = QgsFeatureRequest().setFilterFid(x[y])							# create request to select OSM candidate
		 		OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()				# select OSM candidate
		 		OSM_geom=OSMcandidate.geometry().asPolyline()								# save OSM geometry as Polyline to variable
		 		OSM_P1=OSM_geom[0]															# save first point of OSM segment
		 		OSM_P2=OSM_geom[-1]															# save last point of OSM segment
				dist1=LineString([(LM_P1.x(),LM_P1.y()),(OSM_P2.x(),OSM_P2.y())]).length+LineString([(LM_P2.x(),LM_P2.y()),(OSM_P1.x(),OSM_P1.y())]).length
				dist2=LineString([(LM_P1.x(),LM_P1.y()),(OSM_P1.x(),OSM_P1.y())]).length+LineString([(LM_P2.x(),LM_P2.y()),(OSM_P2.x(),OSM_P2.y())]).length
				short_dist=min(dist1,dist2)
		 		dist_list.append(short_dist)											# add shortest distance between two segments to list										
		 	if dist_list:																# if distance list is not empty
		 		nearst_candidate=dist_list.index(min(dist_list))+1 						# find OSM candidate with shortest distance to LM
				LM_segment_layer.changeAttributeValue(x[0],LMSeg_matchID_pos,x[nearst_candidate])				# add matching OSM Id to LM segment layer to matchid attribute field
				OSMrequest = QgsFeatureRequest().setFilterFid(x[nearst_candidate])								# create request to select OSM candidate
			 	OSMcandidate = OSM_segment_layer.getFeatures(OSMrequest).next()									# select OSM candidate
				LM_segment_layer.changeAttributeValue(x[0],LMSeg_matchFeatId_pos,OSMcandidate["featureId"])		# add Id of matchings segments feature to LM segment layer to matchid attribute field
				OSM_match_dic[OSMcandidate.id()].append([LMcandidate.id(),LMcandidate["featureId"],4])			# add LM feature match id as value to key matching OSM segment
				del candidatelist[iterat_counter-sum_del_candidates]					# delete LM segment from counter 
				sum_del_candidates=sum_del_candidates+1                					# sum_del_candidates plus 1
				match_length_step_LM[4]+=LMcandidate.geometry().length()					# add feature length to matching length step 4
			iterat_counter=iterat_counter+1 										# iteration counter plus 1

		### update OSM segment with matching information:
		for d in OSM_match_dic.items():												# for each key value pair in OSM_match_dic
			if sum([d[1][i].count(d[1][0][1]) for i in range(0,len(d[1]))]) == len(d[1]):				# if all mathing LM segments belong to same LM feature
				LM_match_id=str([str(n[0]) for n in d[1]]).strip("[]").translate(None,"'")						# convert dic value to string and remove [] and ''
				OSM_segment_layer.changeAttributeValue(d[0],OSMSeg_matchID_pos,LM_match_id)						# add matching LM segments Id to OSM segment layer
				OSM_segment_layer.changeAttributeValue(d[0],OSMSeg_matchFeatId_pos,d[1][0][1])					# add  feature id of matching LM segments Id to OSM segment layer
				OSMrequest = QgsFeatureRequest().setFilterFid(d[0])								# create request to select OSM candidate
			 	OSMsegment = OSM_segment_layer.getFeatures(OSMrequest).next()									# select OSM candidate
				match_length_step_OSM[d[1][0][2]]+=OSMsegment.geometry().length()
		#candidatelist_4=list(candidatelist) 							# create copy of candidatelist
		#print len(candidatelist),"5"
		OSM_segment_layer.commitChanges()								# save all edits
		LM_segment_layer.commitChanges()								# save all edits

		# Stage 5: recompose to feature level and match classification
		##############################################################
		# Recompose LM segments:
		LM_features=LM_feature_layer.getFeatures()						# make LM feature layer iterable
		LM_feature_layer.startEditing()									# make LM feature layer editable
		for LMfeature in LM_features:									# for each feature in LM feature layer, do:
		 	feat_length=LMfeature.geometry().length()							# get length of feature
		 	match_dist=0														# create variable to store length of matched segments
		 	match_dic={} 														# create dictionary to store length of matched segments for different features
		 	match_feat_length=[]												# list to store length of possible matching OSM features
		 	match_feat_dic={}													# dictonary to store length and Id information of possible matching OSM features
		 	Id=str(LMfeature[attri_id_clip_LM])										# get Id of LM feature
		 	str_express='"featureId"='+Id 										# formulate expression to select all LM segments belonging to LM feature as string
		 	uni_express=str_express.decode('unicode-escape')					# convert string expression to unicode
		 	Features_segments = LM_segment_layer.getFeatures(QgsFeatureRequest().setFilterExpression(uni_express))  # select all LM segments with LM feature id
		 	for segment in Features_segments:																		# for all segments 
		 		if segment["matchId"]!= NULL:																			# if segment is matched
		 			match_dist=match_dist+segment.geometry().length()														# add length of segment to match distance
		  			if str(segment["matchFeatI"]) in match_dic:																# if feature id of segment is in dic
		 				match_dic[str(segment["matchFeatI"])]+=segment.geometry().length()										# add segment length to key value
		 			else:																									# if not
		 				match_dic[str(segment["matchFeatI"])]=segment.geometry().length()										# create key value (feature of segment) + segment length as value
		 	if match_dist>0.5*feat_length:																			# if half of feature distance has a matched segments, do
		 		if len(match_dic)==1:																					# if only one matching OSM feature
			 		OSM_match=str(match_dic.keys()).strip("[]").translate(None,"'")											# get key(OSM match id) and convert to string
			 		LM_feature_layer.changeAttributeValue(LMfeature.id(),LMFeat_OSMmatch_pos,OSM_match)						# add matching OSM feature to LM feature
		  			match_length_step_LM[5]+=LMfeature.geometry().length()														# add feature length to matching length step 5
		 		elif len(match_dic)>1:																					# if more than one possible matching OSM feature
		 			for k in match_dic.keys():																				# for all OSM features
		 				Id=str(k)																							# selct OSM featutre with id_clip
		 				str_express=attri_id_clip_OSM+'='+Id 																		# formulate expression to select all LM segments belonging to LM feature as string
		 				uni_express=str_express.decode('unicode-escape')													# convert string expression to unicode
		 				OSMcandidate = OSM_feature_layer.getFeatures(QgsFeatureRequest().setFilterExpression(uni_express)).next()  # select all LM segments with LM feature id
		 				#OSMrequest = QgsFeatureRequest().setFilterFid(int(k))													# create request to select OSM candidate
			  	 		#OSMcandidate = OSM_feature_layer.getFeatures(OSMrequest).next()										# select OSM candidate
			  	 		match_feat_length.append(OSMcandidate.geometry().length())												# add length of OSM feature to match_feat_length list
			  	 		if k in match_feat_dic:																					# if feature id is in dic
		 					match_feat_dic[k]+=OSMcandidate.geometry().length()														# add feature length to key value
		 				else:																									# if not
		 					match_feat_dic[k]=OSMcandidate.geometry().length()														# create key value (feature id) + feature length as value
			  	 	match_procent=[(match_feat/feat_length) for match_feat in match_feat_length]								# calculte the length proporation of all possible OSM features to LM feature length
			  	 	candidate_dic={}																							# create dictonary to store matching candidates
			  	 	for l in range(1, len(match_procent)+1):																	# for each item in length match_procent
			  	 		for combination in itertools.combinations(match_procent, l):												# calculate all possible combinations of list items
			  	 			if 0.8<=sum(combination)<=1.2:																				# if sum of values of a combination is between 0.8 and 1.2
			  	 				features=str()																									# create stirng to store OSM feature information
			  	 				for f in combination:																							# for all values of a combination
			  	 					features+=str(match_feat_dic.keys()[match_feat_dic.values().index(match_feat_length[match_procent.index(f)])])+"," 	# get respectively OSM feature id of value											
				 				features=features[:-1]																							# remove last "," of string
				 				feature_ids=[int(i) for i in features.split(',')]																# convert feature ids to list of intgers
				 				feat_geom=[]																									# create list to store geometry of features
				 				# check if combination of features share a common point 
				 				for feat_id in feature_ids:																						# for each feature
				 					Id=str(feat_id)																								# selct OSM featutre with id_clip
		 							str_express=attri_id_clip_OSM+'='+Id 																				# formulate expression to select all OSM segments belonging to OSM feature as string
		 							uni_express=str_express.decode('unicode-escape')															# convert string expression to unicode
		 							OSMcandidate = OSM_feature_layer.getFeatures(QgsFeatureRequest().setFilterExpression(uni_express)).next()  # select all OSM segments with OSM feature id
				 					#OSMrequest = QgsFeatureRequest().setFilterFid(feat_id)															# create request to select LM candidate
		 							#OSMcandidate = OSM_feature_layer.getFeatures(OSMrequest).next()													# select LM candidate
		 							feat_geom.append(OSMcandidate.geometry().asPolyline())															# add feature geometry to list
		 						feat_geom_SE=[[feat[0],feat[-1]]for feat in feat_geom]															# copy only start and end point of each feature to new list
								SP=feat_geom_SE[0][0]																							# select first point of first feature as start point
								EP=feat_geom_SE[0][1]																							# select second point of first feature as start point
								remain_features=list(feat_geom_SE[1:])																			# create list with features except the first
								adjecent=1 																										# create adjecent variable and set to 1, 1 means that combination of features are adjecent, 0 they are not
								while remain_features:																							# until remaing feature list is empty
									for feat in remain_features:																					# for each feature of remaining features
										found="false"																									# set found varible to false, false=point of feature is not adjecnt to start or end point
										index_SP=1 																										# index of start point, to set new start point in case a feature is adjecent
								 		index_EP=1 																										# index of end point, to set new end point in case a feature is adjecent
										for point in feat:																								# for each point in feature
											if point==SP:																									# if point is equal to start point
												SP=feat[index_SP]																								# set new start point, the other point of a feature
												del remain_features[remain_features.index(feat)]																# delete feature from remaining list
												found="true"																									# set found = true
												break																											# break loop through points of feature
											elif point ==EP:																								# if point is equal to end point
												EP=feat[index_EP] 																								# set new end point, the other point of a feature
												del remain_features[remain_features.index(feat)] 																# delete feature from remaining list
												found="ture" 																									# set found = true
												break																											# break loop through points of feature
											index_SP=0 																										# set start point index the other point
											index_EP=0																										# set end point index the other point
										if found=="true":																								# if found is true, after iteration over points of feature
											break																											# break loop over features in remaining list
									if found=="false":																								# if loop over feature found no adjecent feature
										adjecent=0																										# set adjecent to 0
										break																											# break while loop	
		 						if adjecent==1:																								# if combination of features is adjecent
		 							candidate_dic[features]=sum(combination)																	# add features and combination value to dict
				 	if candidate_dic:																							# if candidate dic is not empty
				 		matching_OSM_features=candidate_dic.keys()[candidate_dic.values().index(min(candidate_dic.values(), key=lambda x:abs(x-1)))]	# get key whos value is closest to one, key is matching OSM features
				 		LM_feature_layer.changeAttributeValue(LMfeature.id(),LMFeat_OSMmatch_pos,matching_OSM_features)									# add Id of matching OSM features to LM feature layer 
						match_length_step_LM[5]+=LMfeature.geometry().length()																				# add feature length to matching length step 5
		LM_feature_layer.commitChanges()								# save changes of LM feature Layer


		# Recompose OSM segments:
		OSM_features=OSM_feature_layer.getFeatures()						# make LM feature layer iterable
		OSM_feature_layer.startEditing()									# make LM feature layer editable
		for OSMfeature in OSM_features:										# for each feature in LM feature layer, do:
		 	feat_length=OSMfeature.geometry().length()																# get length of feature
		 	match_dist=0 																							# create variable to store length of matched segments
		 	match_dic={} 																							# create dictionary to store length of matched segments for different features
		 	match_feat_length=[]																					# list to store length of possible matching LM features
		 	match_feat_dic={}																						# dictonary to store length and Id information of possible matching LM features
		 	Id=str(OSMfeature[attri_id_clip_OSM])																			# get Id of OSM feature
		 	str_express='"featureId"='+Id 																			# formulate expression to select all OSM segments belonging to OSM feature as string
		 	uni_express=str_express.decode('unicode-escape')														# convert string expression to unicode
		 	Features_segments = OSM_segment_layer.getFeatures(QgsFeatureRequest().setFilterExpression(uni_express)) # select all OSM segments with OSM feature id
		 	for segment in Features_segments:																		# for all segments 
		 		if segment["matchId"]!= NULL: 																			# if segment is matched
		 			match_dist=match_dist+segment.geometry().length()														# add length of segment to match distance
		 			if str(segment["matchFeatI"]) in match_dic:																# if feature id of segment is in dic
		 				match_dic[str(segment["matchFeatI"])]+=segment.geometry().length()										# add segment length to key value
		 			else:																									# if not
		 				match_dic[str(segment["matchFeatI"])]=segment.geometry().length()										# create key value (feature of segment) + segment length as value
		 	if match_dist>0.5*feat_length:																			# if half of feature distance has a matched segments, do
		 		if len(match_dic)==1:																					# if only one matching LM feature
			 		LM_match=str(match_dic.keys()).strip("[]").translate(None,"'")											# get key(LM match id) and convert it to string
			 		OSM_feature_layer.changeAttributeValue(OSMfeature.id(),OSMFeat_LMmatch_pos,LM_match)					# add matching LM feature to OSM feature
			 		match_length_step_OSM[5]+=OSMfeature.geometry().length()
			 	elif len(match_dic)>1:																					# if more than one possible matching LM features
		 			for k in match_dic.keys():																				# for all LM feature
		 				Id=str(k)																								# selct LM featutre with id_clip
		 				str_express=attri_id_clip_LM+'='+Id 																			# formulate expression to select all LM segments belonging to LM feature as string
		 				uni_express=str_express.decode('unicode-escape')														# convert string expression to unicode
		 				LMcandidate = LM_feature_layer.getFeatures(QgsFeatureRequest().setFilterExpression(uni_express)).next() # select all LM segments with LM feature id
		 				#LMrequest = QgsFeatureRequest().setFilterFid(int(k))													# create request to select LM candidate
			  	 		#LMcandidate = LM_feature_layer.getFeatures(LMrequest).next()											# select LM candidate
			  	 		match_feat_length.append(LMcandidate.geometry().length())												# add length of LM feature to match_feat_length list
			  	 		if k in match_feat_dic:																					# if feature id is in dic
		 					match_feat_dic[k]+=LMcandidate.geometry().length()														# add feature length to key value
		 				else:																									# if not
		 					match_feat_dic[k]=LMcandidate.geometry().length()														# create key value (feature id) + feature length as value
					#print OSMfeature.id(), feat_length, match_dic, int(match_dic.keys()[match_dic.values().index(max(match_dic.values()))]), match_feat_length,[(match_feat/feat_length) for match_feat in match_feat_length] 
			  	 	match_procent=[(match_feat/feat_length) for match_feat in match_feat_length] 								# calculte the length proporation of all possible LM features to OSM feature length
			  	 	candidate_dic={}																							# create dictonary to store matching candidates
			  	 	for l in range(1, len(match_procent)+1):																	# for each item in length match_procent
			  	 		for combination in itertools.combinations(match_procent, l):												# calculate all possible combinations of list items
			  	 			if 0.8<=sum(combination)<=1.2:																						# if sum of values of a combination is between 0.8 and 1.2
			  	 				features=str()																									# create stirng to store LM feature information
			  	 				for f in combination:																							# for all values of a combination
			  	 					features+=str(match_feat_dic.keys()[match_feat_dic.values().index(match_feat_length[match_procent.index(f)])])+","		# get respectively LM feature id of value											
				 				features=features[:-1]																							# remove last "," of string
				 				feature_ids=[int(i) for i in features.split(',')]																# convert feature ids to list of intgers
				 				feat_geom=[]																									# create list to store geometry of features
				 				# check if combination of features share a common point 
				 				for feat_id in feature_ids:																						# for each feature
							 		Id=str(feat_id)																								# selct LM featutre with id_clip
					 				str_express=attri_id_clip_LM+'='+Id 																			# formulate expression to select all LM segments belonging to LM feature as string
					 				uni_express=str_express.decode('unicode-escape')														# convert string expression to unicode
					 				LMcandidate = LM_feature_layer.getFeatures(QgsFeatureRequest().setFilterExpression(uni_express)).next() # select all LM segments with LM feature id
				 					#LMrequest = QgsFeatureRequest().setFilterFid(feat_id)															# create request to select LM candidate
		 							#Mcandidate = LM_feature_layer.getFeatures(LMrequest).next()													# select LM candidate
		 							feat_geom.append(LMcandidate.geometry().asPolyline())															# add feature geometry to list
		 						feat_geom_SE=[[feat[0],feat[-1]]for feat in feat_geom]															# copy only start and end point of each feature to new list
								SP=feat_geom_SE[0][0]																							# select first point of first feature as start point
								EP=feat_geom_SE[0][1]																							# select second point of first feature as start point
								remain_features=list(feat_geom_SE[1:])																			# create list with features except the first
								adjecent=1 																										# create adjecent variable and set to 1, 1 means that combination of features are adjecent, 0 they are not
								while remain_features:																							# until remaing feature list is empty
									for feat in remain_features:																					# for each feature of remaining features
										found="false"																									# set found varible to false, false=point of feature is not adjecnt to start or end point
										index_SP=1 																										# index of start point, to set new start point in case a feature is adjecent
								 		index_EP=1 																										# index of end point, to set new end point in case a feature is adjecent
										for point in feat:																								# for each point in feature
											if point==SP:																									# if point is equal to start point
												SP=feat[index_SP]																								# set new start point, the other point of a feature
												del remain_features[remain_features.index(feat)]																# delete feature from remaining list
												found="true"																									# set found = true
												break																											# break loop through points of feature
											elif point ==EP:																								# if point is equal to end point
												EP=feat[index_EP] 																								# set new end point, the other point of a feature
												del remain_features[remain_features.index(feat)] 																# delete feature from remaining list
												found="ture" 																									# set found = true
												break																											# break loop through points of feature
											index_SP=0 																										# set start point index the other point
											index_EP=0																										# set end point index the other point
										if found=="true":																								# if found is true, after iteration over points of feature
											break																											# break loop over features in remaining list
									if found=="false":																								# if loop over feature found no adjecent feature
										adjecent=0																										# set adjecent to 0
										break																											# break while loop	
		 						if adjecent==1:																								# if combination of features is adjecent
		 							candidate_dic[features]=sum(combination)																	# add features and combination value to dict																	# add LM features (as key) and their combined match_procent value (as value) to dictionary
				 	if candidate_dic:																							# if candidate dic is not empty
				 		matching_LM_features=candidate_dic.keys()[candidate_dic.values().index(min(candidate_dic.values(), key=lambda x:abs(x-1)))]	 	# get key whos value is closest to one, key is matching LM features
				 		OSM_feature_layer.changeAttributeValue(OSMfeature.id(),OSMFeat_LMmatch_pos,matching_LM_features)						 	 	# add Id of matching LM features to OSM feature layer 
						match_length_step_OSM[5]+=OSMfeature.geometry().length()
		OSM_feature_layer.commitChanges()								# save changes of OSM feature Layer
		#print "finish step one"

		#Stage 6: OSM feature matching depending on distance and name
		#############################################################
		#create new candidatelist
		OSM_features=OSM_feature_layer.getFeatures() 					# make OSM layer iterable
		counter=0 														# create counter
		candidatelist=[]												# create empty candidate list
		for OSMfeature in OSM_features:									# for each OSM feature
			if OSMfeature[attri_match_OSM] == NULL:							# only for none matched OSM features, do
				candidatelist.append([OSMfeature.id()])					# update candidate list in fowling iterations 
				Buffer=OSMfeature.geometry().buffer(GPS_accuracy,100)					# create 10 meter (GPS accuracy) buffer
				LM_features=LM_feature_layer.getFeatures() 					# make LM layer iterable
				for LMfeature in LM_features:								# for each LM feature
					if LMfeature.geometry().within(Buffer) == True:				# check if it is within buffer
						candidatelist[counter].append(LMfeature.id())				# if yes, assign feature id to list of LM candidates
				counter+=1
		#print candidatelist
		#print len(candidatelist),"6"
		#candidatelist_6_start=list(candidatelist) 						# save copy of candidatelist

		# check name similarity
		iterat_list=list(candidatelist)									# create copy of list to use to iterate over
		iterat_counter=0                                                # iteration counter
		sum_del_candidates=0 											# counter to keep track of number of deleted LM candidates
		LM_match_dic=defaultdict(list)									# create list dictionary to store OSM feature match id's
		OSM_feature_layer.startEditing()								# make OSM feature layer editable
		for x in iterat_list:											# for each candidate
			OSMrequest = QgsFeatureRequest().setFilterFid(x[0])						# create request to select OSM candidate
			OSMfeature = OSM_feature_layer.getFeatures(OSMrequest).next()			# select OSM candidate
			similar_name_value=[]													# list to store values of name similarity measurment
			if OSMfeature[attri_name_OSM]==NULL:											# if OSM feature has no name attribute
				iterat_counter=iterat_counter+1									# iteration counter plus 1
			else:																	# if OSM feature has name
				OSM_name=OSMfeature[attri_name_OSM].encode(encoding_OSM)								# OSM name to string in latin-1 encoding
		 		OSM_name=OSM_name.upper()													# make name only upper cases
		 		for y in range(1,len(x)):													# for each LM candidate
					LMrequest = QgsFeatureRequest().setFilterFid(x[y])							# create request to select LM candidate
		 			LMcandidate = LM_feature_layer.getFeatures(LMrequest).next()				# select LM candidate
		 			if LMcandidate[attri_name_LM]==NULL:												# if LM candidate has no name
		 				similar_name_value.append(0.0)												# add name similarity value of 0
		 			else:																		# if LM candidate has name
			 			LM_name=LMcandidate[attri_name_LM].encode(encoding_LM)								# LM name to string in Latin-1 encoding
						LM_name=LM_name.upper()														# make name only upper cases
						max_length=max(len(LM_name),len(OSM_name))									# get maximum length of LM or OSM name
				 		similar_match=1-(metrics.edit_distance(OSM_name, LM_name)/float(max_length))# calculate similar character measurement (levenshtein distance in percentage)
				 		similar_name_value.append(similar_match)									# add value to similar name value list
			 	if similar_name_value:														# if similar name value list is not empty		
				 	LM_match_id=[]																# create list to store matching LM feature id
				 	counter=0 																	# intialise counter
					for v in similar_name_value:												# for all similar values
						if v >NS_threshold_S6:																		# if value above 0.8
							LM_match_id.append(x[counter+1])												# add to LM feature id to match list
							counter+=1 																		# increase counter by 1
						else:																			# if value below 0.8
							counter+=1 																		# increase counter by 1	
					LM_match_clip_id=[]
					for f in LM_match_id:
						LMrequest = QgsFeatureRequest().setFilterFid(f)								# create request to select LM feature
						LMcandidate = LM_feature_layer.getFeatures(LMrequest).next()					# select LM feature
						LM_match_clip_id.append([LMcandidate[attri_id_clip_LM]])
					LM_match_clip_id_STR=str([' '.join(str(b) for b in a) for a in LM_match_clip_id]).strip("[]").translate(None,"'")
					#LM_match_clip_id_STR=str([str(n) for n in LM_match_clip_id]).strip("[]").translate(None,"'")	# convert list to string and remove [] and '	
					#print LM_match_clip_id, LM_match_clip_id_STR
					#LM_match_clip_id_STR=LM_match_clip_id_STR.strip("[]")
					OSM_feature_layer.changeAttributeValue(OSMfeature.id(),OSMFeat_LMmatch_pos,LM_match_clip_id_STR)	# add matching LM Ids to OSM feature layer to matchid attribute field
					for f in LM_match_id:																# for all LM matches, do
						#OSMrequest = QgsFeatureRequest().setFilterFid(f)								# create request to select LM feature
						#OSMcandidate = OSM_feature_layer.getFeatures(OSMrequest).next()					# select LM feature
						LM_match_dic[f].append(OSMfeature[attri_id_clip_OSM])										# add LM feature match id as key with value of OSM feature
					del candidatelist[iterat_counter-sum_del_candidates]								# delete OSM feature from candidatelist
					sum_del_candidates+=1                												# sum_del_candidates plus 1
				iterat_counter+=1 																# iterate_counter+1
		OSM_feature_layer.commitChanges()													# save changes of OSM feature Layer

		LM_feature_layer.startEditing()													# make LM feature layer editableprint LM_match_dic
		for d in LM_match_dic.items():													# for all keys in dic
			OSM_match_id=str([str(n) for n in d[1]]).strip("[]").translate(None,"'")		# convert dic value to string and remove [] and ''
			LM_feature_layer.changeAttributeValue(d[0],LMFeat_OSMmatch_pos,OSM_match_id)	# add matching OSM Ids to LM feature layer to matchid attribute field
		LM_feature_layer.commitChanges()												# save changes of OSM feature Layer

		#candidatelist_6_end=list(candidatelist)								# save copy of candidatelist
		
		# calculate matching length of step 5 	
		LM_features=LM_feature_layer.getFeatures() 					# make LM layer iterable
		for LMfeature in LM_features:									# for each LM feature
			if LMfeature[attri_match_LM] != NULL:							# only for matched LM features, do
				match_length_step_LM[6]+=LMfeature.geometry().length()			# add feature length to matching length step 6

			# for OSM
		OSM_features=OSM_feature_layer.getFeatures() 					# make OSM layer iterable
		for OSMfeature in OSM_features:									# for each OSM feature
			if OSMfeature[attri_match_OSM] != NULL:							# only for matched OSM features,
				match_length_step_OSM[6]+=OSMfeature.geometry().length()		# add feature lentgh to total matched length
		
		
		#print candidatelist
		#print len(candidatelist),"7"

		#Stage 7: Check if matching information exit in corresponding layer
		###################################################################
		# checks all OSM features without match, if feature is a match of a LM feature
		OSM_feature_layer.startEditing()							# make OSM feature layer editable
		match_dic_OSM=defaultdict(list)								# create dic to store LM matches for OSM feature
		OSM_features=OSM_feature_layer.getFeatures()				# make OSM feature layer iterable
		for OSMfeature in OSM_features:								# for each feature in OSM feature layer, do:	
			if OSMfeature[attri_match_OSM]==NULL:							# if OSM feature is nor matched
				LM_features=LM_feature_layer.getFeatures()						# make LM feature layer iterable
				for LMfeature in LM_features:									# for all LM features
					if LMfeature[attri_match_LM]!=NULL:									# if LM fature is matched
						LM_match=[int(i) for i in LMfeature[attri_match_LM].strip('{}').split(',')]	# save match id's as integers
						for m in LM_match: 															# for each match id 
							if m==OSMfeature[attri_id_clip_OSM]:														# if match id is the same as OSM feature id
								match_dic_OSM[OSMfeature.id()].append(str(LMfeature[attri_id_clip_LM]))					# add LM feature id as value to OSM feature id key

		for c in match_dic_OSM.items():								# for all dic items
			LM_match=str([str(n) for n in c[1]]).strip("[]").translate(None,"'")		# convert dic value to string and remove [] and ''
		 	OSM_feature_layer.changeAttributeValue(c[0],OSMFeat_LMmatch_pos,LM_match)	# add matching LM id's to OSM feature layer to LM_match attribute field
			OSMrequest = QgsFeatureRequest().setFilterFid(c[0])						# create request to select OSM candidate
			OSMfeature = OSM_feature_layer.getFeatures(OSMrequest).next()			# select OSM candidate
			match_length_step_OSM[7]+=OSMfeature.geometry().length()
		OSM_feature_layer.commitChanges()							# save changes of OSM feature Layer


		# checks all LM features without match, if feature is a match of a OSM feature
		LM_feature_layer.startEditing()								# make LM feature layer editable
		match_dic_LM=defaultdict(list)								# create dic to store OSM matches for LM feature
		LM_features=LM_feature_layer.getFeatures()					# make LM feature layer iterable
		for LMfeature in LM_features:								# for each feature in LM feature layer, do:	
			if LMfeature[attri_match_LM]==NULL:							# if LM feature is not matched
				OSM_features=OSM_feature_layer.getFeatures()					# make LM feature layer iterable
				for OSMfeature in OSM_features:									# for all OSM features
					if OSMfeature[attri_match_OSM]!=NULL:									# if OSM feature is matched
						OSM_match_ids=[int(i) for i in OSMfeature[attri_match_OSM].strip('{}').split(',')]	# save match id's as integers
						for m in OSM_match_ids:															# for each match id 
							if m==LMfeature[attri_id_clip_LM]:															# if match id is the same as LM feature id
		 						match_dic_LM[LMfeature.id()].append(str(OSMfeature[attri_id_clip_OSM]))						# add OSM feature id as value to LM feature id key

		for c in match_dic_LM.items():								# for all dic items
			OSM_match=str([str(n) for n in c[1]]).strip("[]").translate(None,"'")		# convert dic value to string and remove [] and ''
		 	LM_feature_layer.changeAttributeValue(c[0],LMFeat_OSMmatch_pos,OSM_match)	# add matching OSM id's to LM feature layer to OSM_match attribute field
			LMrequest = QgsFeatureRequest().setFilterFid(c[0])								# create request to select LM feature
			LMcandidate = LM_feature_layer.getFeatures(LMrequest).next()					# select LM feature
			match_length_step_LM[7]+=LMcandidate.geometry().length()
		LM_feature_layer.commitChanges()							# save changes of LM feature Layer
		
		# calculate total matching length	
		# for LM
		LM_features=LM_feature_layer.getFeatures() 					# make LM layer iterable
		for LMfeature in LM_features:									# for each LM feature
			if LMfeature[attri_match_LM] != NULL:							# only for matched LM features,
				total_match_length_feat_LM+=LMfeature.geometry().length()		# add feature lentgh to total matched length
		# for OSM
		OSM_features=OSM_feature_layer.getFeatures() 					# make OSM layer iterable
		for OSMfeature in OSM_features:									# for each OSM feature
			if OSMfeature[attri_match_OSM] != NULL:							# only for matched OSM features,
				total_match_length_feat_OSM+=OSMfeature.geometry().length()		# add feature lentgh to total matched length
		

		# transfer match attribute information form matched simplified feature layer to orginal feature layer
		Dir_Org_OSM=Dir_OUT_Feat+"OSM_Feat_"+str(Tile[attri_id_tile])+".shp"
		Dir_Org_LM=Dir_OUT_Feat+"LM_Feat_"+str(Tile[attri_id_tile])+".shp"
		LM_original_layer=QgsVectorLayer(Dir_Org_LM, "OSM_features", "ogr")
		OSM_original_layer=QgsVectorLayer(Dir_Org_OSM, "OSM_features", "ogr")
		# add match info to LM orginal layer
		LM_feature_counter=0
		LM_original_layer.startEditing()								# make LM orginal layer editable
		LM_originals=LM_original_layer.getFeatures()					# make LM orginal layer iterable
		for LMoriginal in LM_originals:									# for each feature in LM orginal layer, do:	
			LM_feature_counter+=1
			LM_features=LM_feature_layer.getFeatures()						# make LM feature layer iterable
			for LMfeature in LM_features:									# for each feature in LM feature layer, do:
				if LMfeature[attri_id_clip_LM]==LMoriginal[attri_id_clip_LM]:					# if feature is the sama as in orginal feaute
					LM_original_layer.changeAttributeValue(LMoriginal.id(),LMFeat_OSMmatch_pos,LMfeature[attri_match_LM]) # copy match information to original feature
		LM_original_layer.commitChanges()								# save changes of LM original Layer
		
		OSM_feature_counter=0
		OSM_original_layer.startEditing()								# make OSM orginal layer editable
		OSM_originals=OSM_original_layer.getFeatures()						# make OSM orginal layer iterable
		for OSMoriginal in OSM_originals:									# for each feature in OSM orginal layer, do:	
			OSM_feature_counter+=1
			OSM_features=OSM_feature_layer.getFeatures()						# make OSM feature layer iterable
			for OSMfeature in OSM_features:									# for each feature in OSM feature layer, do:
				if OSMfeature[attri_id_clip_OSM]==OSMoriginal[attri_id_clip_OSM]:					# if feature is the sama as in orginal feaute
					OSM_original_layer.changeAttributeValue(OSMoriginal.id(),OSMFeat_LMmatch_pos,OSMfeature[attri_match_OSM]) # copy match information to original feature			
		OSM_original_layer.commitChanges()								# save changes of OSM original Layer
		
		# clip LM roads file to tile extent
		# clip LM to actual tile exten
	 	processing.runalg("qgis:clip",Dir_Org_LM,Dir_temp+"tile"+str(Tile["ID"])+".shp",Dir_OUT_Feat+"LM_Feat_"+str(Tile[attri_id_tile])+"_clip.shp")
	 	# clip OSM road file to tile extent
		processing.runalg("qgis:clip",Dir_Org_OSM,Dir_temp+"tile"+str(Tile["ID"])+".shp",Dir_OUT_Feat+"OSM_Feat_"+str(Tile[attri_id_tile])+"_clip.shp")
		time_matching_tile=time.time()
		
		# calculate matching percentages
		#***********************************
		Dir_OSM=Dir_OUT_Feat+"OSM_Feat_"+str(Tile[attri_id_tile])+"_clip.shp"
		Dir_LM=Dir_OUT_Feat+"LM_Feat_"+str(Tile[attri_id_tile])+"_clip.shp"
		OSM_feature_layer=QgsVectorLayer(Dir_OSM, "OSM_features", "ogr")
		LM_feature_layer=QgsVectorLayer(Dir_LM, "LM_features", "ogr")
		
		# match percentage LM layer
		total_lentgh=0
		matched_length=0
		LM_features=LM_feature_layer.getFeatures()					# make LM feature layer iterable
		for LMfeature in LM_features:
			total_lentgh+=LMfeature.geometry().length()
			if LMfeature[attri_match_LM]!=NULL:
				matched_length+=LMfeature.geometry().length()
		total_length_LM_SA+=total_lentgh
		total_match_length_LM_SA+=matched_length
		if total_lentgh !=0:
			match_per=matched_length/total_lentgh
			Tile_layer.startEditing()
			Tile_layer.changeAttributeValue(Tile.id(),Tile_LMmatch_pos,match_per)
		
		#match percentage OSM layer
		total_lentgh=0
		matched_length=0
		OSM_features=OSM_feature_layer.getFeatures()					# make LM feature layer iterable
		for OSMfeature in OSM_features:
			total_lentgh+=OSMfeature.geometry().length()
			if OSMfeature[attri_match_OSM]!=NULL:
				matched_length+=OSMfeature.geometry().length()
		total_length_OSM_SA+=total_lentgh
		total_match_length_OSM_SA+=matched_length
		if total_lentgh !=0:
			match_per=matched_length/total_lentgh
			Tile_layer.changeAttributeValue(Tile.id(),Tile_OSMmatch_pos,match_per)
			Tile_layer.commitChanges()

		time_end_tile=time.time()
		time_per_tile[Tile[attri_id_tile]].append([LM_feature_counter,OSM_feature_counter,time_matching_tile-time_start_tile,time_end_tile-time_start_tile])
		
	print"finish tile", tile_dir
	print datetime.datetime.now().time()

	# calculate matching statatistics 
	length_per_LM=[]										# store match percentage per step
	length_per_OSM=[]										# store OSM match percentage per step
	# for LM feature
	for step in match_length_step_LM:									# for each matching step, not for creating the candidatelist
		length_per_LM.append(match_length_step_LM[step]/total_match_length_feat_LM)	# calculate matching percentage of length
	length_per_LM[5]=length_per_LM[5]-length_per_LM[4]						# correct matching percentage for step 5
	length_per_LM[4]=length_per_LM[4]-sum(length_per_LM[:4])					# correct matching percentage for step 4
	for step in match_length_step_OSM:									# for each matching step, not for creating the candidatelist
		length_per_OSM.append(match_length_step_OSM[step]/total_match_length_feat_OSM)	# calculate matching percentage of length
	length_per_OSM[5]=length_per_OSM[5]-length_per_OSM[4]						# correct matching percentage for step 5
	length_per_OSM[4]=length_per_OSM[4]-sum(length_per_OSM[:4])					# correct matching percentage for step 4
	
	time_end=time.time()

	# write result varibles to files
	# match result
	with open(Dir_results+'total_length.txt', 'w') as outfile:
		json.dump([total_length_LM_SA,total_match_length_LM_SA,total_length_OSM_SA,total_match_length_OSM_SA], outfile)
	with open(Dir_results+'time.txt', 'w') as outfile:
		json.dump([time_start, time_end], outfile)
	with open(Dir_results+'time_per_tile.txt', 'w') as outfile:
		json.dump(time_per_tile, outfile)
	with open(Dir_results+'length_per_LM.txt', 'w') as outfile:
		json.dump(length_per_LM, outfile)
	with open(Dir_results+'length_per_OSM.txt', 'w') as outfile:
		json.dump(length_per_OSM, outfile)

	print "finish complete"
	print datetime.datetime.now().time()	