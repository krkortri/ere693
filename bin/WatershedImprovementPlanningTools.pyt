# Lab 6 Updates by Kyle Kortright
# GIS-Based Modeling
# 3/8/16

# This code contains script that was created by converting the Modelbuilder results
# from ArcMap to a python script. The syntax was modified slightly in order to operate correctly.

import os, sys, shutil, arcpy
import traceback, time
from arcpy import env

def log(message):
    arcpy.AddMessage(message)
    with file(sys.argv[0]+".log", 'a') as logFile:
        logFile.write("%s:\t%s\n" % (time.asctime(), message))
    
class Toolbox(object):
    def __init__(self):
        self.label = "WIP tools"
        self.alias = ""
        self.tools = [TopoHydro, ImpCov, Runoff]
        
class TopoHydro(object):
    def __init__(self):
        self.label = "Topography and Hydrology Analysis"
        self.description = "Establishes the watershed and stream network"
        self.canRunInBackground = False
        
        arcpy.env.Workspace = self.Workspace = os.path.split(__file__)[0]
        log("Workspace = " + arcpy.env.Workspace)
        arcpy.env.overwriteOutput = True       

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        param0 = arcpy.Parameter(
            displayName="Input Digital Elevation Model",
            name="DEM",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input",
            multiValue=False)  
            
        param1 = arcpy.Parameter(
            displayName="Analysis Mask",
            name="Mask",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input",
            multiValue=False)  
        
        param2 = arcpy.Parameter(
            displayName="Threshold accumulation for Stream formation (acres)",
            name="StreamFormation",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            multiValue=False)  
        
        params = [ param0, param1, param2 ]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return
            
    def execute(self, parameters, messages):
        try:
            log("Parameters are %s, %s, %s" % (parameters[0].valueAsText, parameters[1].valueAsText, parameters[2].valueAsText))
        
			################ TASK 2 ##################

			# Define local variables
			DEM = parameters[0].valuesAsText
			AnalysisMask = parameters[1].valueAsText

			# Set DEM as the snap raster, set mask, set cell size
			arcpy.env.snapRaster = DEM
			arcpy.env.mask = AnalysisMask
			cellsize = arcpy.Describe(DEM).meanCellHeight

			# Convert mask to raster using the "mask" field
			Raster_Mask = arcpy.FeatureToRaster_conversion(AnalysisMask, "mask", cellsize)

			# Fill in the sinks in DEM
			Fill_Sinks = arcpy.gp.Fill_sa(DEM, "")

			# Calculate Flow Direction
			Flow_Direction = arcpy.gp.FlowDirection_sa(Fill_Sinks, "NORMAL", Output_drop_raster)

			# Calculate Flow Accumulation
			Flow_Accumulation = arcpy.gp.FlowAccumulation_sa(Flow_Direction, "", "FLOAT")

			# Convert accumulation to area in acres
			Drainage_Area = arcpy.gp.RasterCalculator_sa("\"%Flow_Accumulation%\"*cellsize*cellsize/43560")

			# Reclassify to distinguish streams (values determined from looking at flow accumulation raster)
			Stream_Network = arcpy.gp.Reclassify_sa(Drainage_Area, "Value", "0 450 NODATA;650 22526.390625 1", "DATA")

			# Create stream feature class
			Streams = arcpy.gp.StreamToFeature_sa(Stream_Network, Flow_Direction, "SIMPLIFY")
		
		except Exception as err:
            log(traceback.format_exc())
            log(err)
            raise err
        return

class ImpCov(object):
    def __init__(self):
        self.label = "Imperviousness Analysis"
        self.description = "Impervious area contributions"
        self.canRunInBackground = False
        
        arcpy.env.Workspace = self.Workspace = os.path.split(__file__)[0]
        log("Workspace = " + arcpy.env.Workspace)
        arcpy.env.overwriteOutput = True       

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        param0 = arcpy.Parameter(
            displayName="Impervious Areas",
            name="ImperviousAreas",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input",
            multiValue=False)  
            
        param1 = arcpy.Parameter(
            displayName="Lakes",
            name="Lakes",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input",
            multiValue=False)  
        
        params = [ param0, param1 ]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return
            
    def execute(self, parameters, messages):
        try:
            log("Parameters are %s, %s, %s, %s, %s, %s" % (parameters[0].valueAsText, parameters[1].valueAsText, parameters[2].valueAsText, parameters[3].valueAsText, parameters[4].valueAsText, parameters[5].valueAsText))
        
			################## TASK 3 #####################

			# Define local variables
            DEM = parameters[0].valuesAsText
            Impervious = parameters[1].valueAsText
			Flow_Direction = parameters[2].valueAsText
			Flow_Accumulation = parameters[3].valueAsText
			Stream_Network = parameters[4].valueAsText

			# Set DEM as snap raster and set cell size to 1/10 of the DEM cell size
			arcpy.env.snapRaster = DEM
			cellsize = float(arcpy.Describe(DEM).meanCellHeight)/10
			
			# Calculate Field length and set = to 1
			LengthField_1 = arcpy.CalculateField_management(Impervious, "LENGTH", "1", "VB", "")

			# Convert feature to raster, use cell size 1/10 of DEM
			Impervious_Areas_Raster = arcpy.FeatureToRaster_conversion(LengthField_1, "LENGTH", "cellsize")

			# Determine block statistics with 10*10
			Block_Statistics = arcpy.gp.BlockStatistics_sa(Impervious_Areas_Raster, "Rectangle 10 10 CELL", "SUM", "DATA")

			# Aggregate block statistics
			Aggregate_Blocked_Data = arcpy.gp.Aggregate_sa(Block_Statistics, "10", "MEAN", "EXPAND", "DATA")

			# Flow accumulation with the weight from the aggregate
			Weighted_Accumulation = arcpy.gp.FlowAccumulation_sa(Flow_Direction, Aggregate_Blocked_Data, "FLOAT")

			# Determine percent of accumulation due to impervious cover
			Impervious_Contribution = arcpy.gp.RasterCalculator_sa("\"%Weighted_Accumulation%\"/\"%Flow_Accumulation%\"")

			# Reclassify into ten groups
			Percent_Contribution = arcpy.gp.Reclassify_sa(Impervious_Contribution, "Value", "0 10 1;10 20 2;20 30 3;30 40 4;40 50 5;50 60 6;60 70 7;70 80 8;80 90 9;90 100 10", "DATA")

			# Divide by 100 to get into percents
			Percentage = arcpy.gp.RasterCalculator_sa(Percent_Contribution, "\"%Percent_Contribution%\"/100")

			# Determine stream networks with percentage of flow from impervious
			Contribution_to_Stream = arcpy.gp.RasterCalculator_sa("\"%Percentage%\"*\"%Stream_Network%\"")

			# Convert stream raster to feature class
			Weighted_Streams = arcpy.gp.StreamToFeature_sa(Contribution_to_Stream, Flow_Direction, "SIMPLIFY")

			################### TASK 4 ######################

			# Define local variables:
            Drainage_Area = parameters[5].valueAsText

            # Set geoprocessing environments
            arcpy.env.extent = Drainage_Area

            # Convert from acres to square miles
            Square_Miles = arcpy.gp.RasterCalculator_sa("Float(\"%Drainage_Area%\"*0.0015625)")

            # Determine 2 year R.I. flows
            two_year = arcpy.gp.RasterCalculator_sa("144*(\"%Square_Miles%\"**0.691)")

            # Urban flow 2 year R.I.
            UF_2year = arcpy.gp.RasterCalculator_sa("7.87*(\"%Square_Miles%\"**0.539)*(\"%Impervious_Contribution%\"**0.686)*(\"%two_year%\"**0.29)")

            # Determine 5 year R.I. flows
            five_year = arcpy.gp.RasterCalculator_sa("248*(\"%Square_Miles%\"**0.670)")

            # Urban flow 5 year R.I.
            UF_5year = arcpy.gp.RasterCalculator_sa("16.3*(\"%Square_Miles%\"**0.489)*(\"%Impervious_Contribution%\"**0.572)*(\"%five_year%\"**0.286)")

            # Determine 10 year R.I. flows
            ten_year = arcpy.gp.RasterCalculator_sa("334*(\"%Square_Miles%\"**0.665)")

            # Urban flow 10 year R.I.
            UF_10year = arcpy.gp.RasterCalculator_sa("22.7*(\"%Square_Miles%\"**0.463)*(\"%Impervious_Contribution%\"**0.515)*(\"%ten_year%\"**0.289)")

            # Determine 25 year R.I. flows
            twentyfive_year = arcpy.gp.RasterCalculator_sa("467*(\"%Square_Miles%\"**0.655)")

            # Urban flow 25 year R.I.
            UF_25year = arcpy.gp.RasterCalculator_sa("28.5*(\"%Square_Miles%\"**0.390)*(\"%Impervious_Contribution%\"**0.436)*(\"%twentyfive_year%\"**0.338)")

            # Determine 50 year R.I. flows
            fifty_year = arcpy.gp.RasterCalculator_sa("581*(\"%Square_Miles%\"**0.650)")

            # Urban flow 50 year R.I.
            UF_50year = arcpy.gp.RasterCalculator_sa("37.4*(\"%Square_Miles%\"**0.391)*(\"%Impervious_Contribution%\"**0.396)*(\"%fifty_year%\"**0.325)")

            # Determine 100 year R.I. flows
            hundred_year = arcpy.gp.RasterCalculator_sa("719*(\"%Square_Miles%\"**0.643)")

            # Urban flow 100 year R.I.
            UF_100year = arcpy.gp.RasterCalculator_sa("48*(\"%Square_Miles%\"**0.392)*(\"%Impervious_Contribution%\"**0.358)*(\"%hundred_year%\"**0.312)")

            # If desired: Each urban flow can be reclassified, multiplied by the stream network, and then converted to a vector stream network to show the difference in flows during each recurrence interval.
		
		except Exception as err:
            log(traceback.format_exc())
            log(err)
            raise err
        return
        
class Runoff(object):
    def __init__(self):
        self.label = "Runoff Calculations"
        self.description = "Calculation of standard storm flows via USGS regression equations"
        self.canRunInBackground = False
        
        arcpy.env.Workspace = self.Workspace = os.path.split(__file__)[0]
        log("Workspace = " + arcpy.env.Workspace)
        arcpy.env.overwriteOutput = True       

    def getParameterInfo(self):
        """Define parameter definitions"""
        
        param0 = arcpy.Parameter(
            displayName="Curve Number",
            name="Landuse",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input",
            multiValue=False)  
        
        params = [ param0 ]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return
            
    def execute(self, parameters, messages):
        try:
            log("Parameter is %s" % (parameters[0].valueAsText))
        except Exception as err:
            log(traceback.format_exc())
            log(err)
            raise err
        return
		
