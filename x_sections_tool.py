from tkinter import *
from PIL import Image, ImageTk
import arcpy

import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

# Default inputs:
default_in_mwstr = 'D:\\x_section_tool_2022\\x_sec_sample_data\\Data.gdb\\Stream'
default_in_dem = 'D:\\x_section_tool_2022\\x_sec_sample_data\\Data.gdb\\dem1m'
default_out_location = 'D:\\x_section_tool_2022\\x_sec_sample_data'

# default_in_mwstr = r'D:\XSecRollOutNov22\Cardinia\Data.gdb\Stream'
# default_in_dem = r'D:\XSecRollOutNov22\Cardinia\Data.gdb\dem1m'
# default_out_location = r'D:\XSecRollOutNov22\Cardinia'


# Define GDA94 MGA Zone 55
proj_gda94z55_def = "PROJCS['GDA_1994_MGA_Zone_55'," \
               "GEOGCS['GCS_GDA_1994',DATUM['D_GDA_1994',SPHEROID['GRS_1980',6378137.0,298.257222101]]," \
               "PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator']," \
               "PARAMETER['False_Easting',500000.0],PARAMETER['False_Northing',10000000.0]," \
               "PARAMETER['Central_Meridian',147.0],PARAMETER['Scale_Factor',0.9996]," \
               "PARAMETER['Latitude_Of_Origin',0.0]," \
               "UNIT['Meter',1.0]];-5120900 1900 10000;-100000 10000;-100000 10000;0.001;0.001;0.001;IsHighPrecision"


# -------------------------------------------------------------------------------------------------------------------
# Main functions
# --------------------------------------------------------------------------------------------------------------------

def main_process():
    # --------------------------------------------
    # Input values
    # --------------------------------------------
    global mwstr
    mwstr = entry_mwstr_path.get()
    dem = entry_dem.get()
    out_loc = entry_out_loc.get()
    interval = entry_interval.get()
    x_sec_width = width_selected.get()
    slope_at = entry_slope.get()
    # --------------------------------------------
    # Validate the input values
    # --------------------------------------------
    if not validate_entries(mwstr, dem, out_loc, interval, slope_at):
        return None
    # --------------------------------------------
    # Check if at least one check box is selected.
    # --------------------------------------------
    if chk_btn_stnpts_var.get() == 0 and chk_btn_2D_x_secs_var.get() == 0 and \
            chk_btn_3D_x_secs_var.get() == 0 and chk_btn_3D_x_secs_slope_lvl_var.get() == 0:
        lbl_status.config(text="Please check at least one model.", fg="red")
        return None
    # --------------------------------------------
    # If above does not return None, set parameters
    # --------------------------------------------
    disable_optons()

    width_plus_1 = int(x_sec_width) + 1
    buffers_list = range(10, width_plus_1, 2)

    station_points_sort_value = len(buffers_list) + 1
    station_distance = interval + " Meters"

    # Set temp paths
    temp_path = create_temp_environ(out_loc)
    global tempGDB 
    tempGDB = temp_path[1]

    # Set Output gdb and outputs
    fgdb = "x_sec_outputs.gdb"
    out_fdb = out_loc + "\\" + fgdb
    if not arcpy.Exists(out_fdb):
        arcpy.CreateFileGDB_management(out_loc, fgdb)

    slope_deg = out_fdb + "\\slope_deg"
    stn_pts = out_fdb + "\\station_points_" + str(interval) + "m"
    x_sec2d = f'{out_fdb}\\x_sec_i{interval}_w{x_sec_width}'
    x_sec3d = x_sec2d + "_3D"
    global x_sec3d_pts
    x_sec3d_pts = x_sec3d + "_pts"

    option_num = None
    if chk_btn_3D_x_secs_slope_lvl_var.get() == 1:
        chk_btn_stnpts_var.set(1)
        chk_btn_2D_x_secs_var.set(1)
        chk_btn_3D_x_secs_var.set(1)
        option_num = 4
    elif chk_btn_3D_x_secs_var.get() == 1:
        chk_btn_stnpts_var.set(1)
        chk_btn_2D_x_secs_var.set(1)
        option_num = 3
    elif chk_btn_2D_x_secs_var.get() == 1:
        chk_btn_stnpts_var.set(1)
        option_num = 2
    elif chk_btn_stnpts_var.get() == 1:
        option_num = 1

    # --------------------------------------------
    # Process - Dissolve mwstr
    # --------------------------------------------
    mwstr_dis = out_fdb + "\\mwstr_segments"
    add_field_with_a_value(mwstr, "ggis_id", "SHORT", 1)

    if not arcpy.Exists(mwstr_dis):
        report_status(f'Processing: mwstr..', "black")
        arcpy.Dissolve_management(in_features=mwstr, out_feature_class=mwstr_dis, dissolve_field="ggis_id",
                                  statistics_fields="", multi_part="SINGLE_PART", unsplit_lines="DISSOLVE_LINES")
        add_field_with_a_value(mwstr_dis, "seg_id", "LONG", '!OBJECTID!')
        report_status(f'Done: Dissolved mwstr : {mwstr_dis}', "green")
    else:
        report_status(f'Using existing: {mwstr_dis}..', "black")

    # --------------------------------------------
    # Based on check boxes selected
    # CASE 1 - Station Points
    # --------------------------------------------
    if option_num in (1, 2, 3, 4):
        # Develop station points - this is mandatory for all options
        # ----------------------------------------------------------
        if not arcpy.Exists(stn_pts):
            report_status(f'Processing: Station Points..', "black")
            station_points(mwstr_dis, stn_pts, station_distance, station_points_sort_value)
            report_status(f'Done: Station Points : {stn_pts}', "green")
        else:
            report_status(f'Using existing station Points.. {stn_pts}..', "black")
    # --------------------------------------------
    # CASE 2 - Develop 2D x-sections
    # --------------------------------------------
    if option_num in (2, 3, 4):
        # Develop 2D x-sections
        # ---------------------
        if not arcpy.Exists(x_sec2d):
            report_status(f'Processing: 2D x-sections..(Takes time)', "red")
            # --------------------------------------------
            # do this for each seg_id in mwstr
            # --------------------------------------------
            merge_string = ""
            cursor = arcpy.SearchCursor(mwstr_dis, ['seg_id'])
            for row in cursor:
                seg_id = row.getValue("seg_id")

                seg_line = tempGDB + "\\seg_line_" + str(seg_id)
                stn_pts_seg = tempGDB + "\\stn_pts_" + str(seg_id)
                x_sec2d_seg = tempGDB + "\\x_sec2d_" + str(seg_id)

                statement = f'seg_id = {seg_id}'
                arcpy.Select_analysis(mwstr_dis, seg_line, statement)
                arcpy.Select_analysis(stn_pts, stn_pts_seg, statement)
                # --------------------------------------------
                # Call function to process 2D x-sections..for a segment
                # --------------------------------------------
                report_status(f'Processing: 2D x-sections..for segment {seg_id} (Takes time. Watch console.)', "red")
                x_sec_2D(seg_line, stn_pts_seg, station_points_sort_value, buffers_list, x_sec2d_seg)

                add_field_with_a_value(x_sec2d_seg, "seg_id", "LONG", seg_id)
                merge_string += ";" + x_sec2d_seg
            # --------------------------------------------
            # Merge all segment-wise cross sections into one.
            # --------------------------------------------
            merge_string = merge_string[1:]
            arcpy.Merge_management(merge_string, x_sec2d, "")

            delete_temps(merge_string.split(";"))
            report_status(f'Done: 2D x_sec : {x_sec2d}', "green")
        else:
            report_status(f'Using existing: {x_sec2d}..', "black")
    # --------------------------------------------
    # CASE 3 - Develop 3D x-sections with info
    # --------------------------------------------
    if option_num in (3, 4):
        # Develop 3D x-sections, points, current centre, new centre and attach slope values
        # ---------------------------------------------------------------------------------
        if not arcpy.Exists(slope_deg):
            # --------------------------------------------
            # Slope in degrees
            # --------------------------------------------
            report_status(f'Processing: Slope in degrees..', "black")
            arcpy.gp.Slope_sa(dem, slope_deg, "DEGREE", "1")
            report_status(f'Done: Slope in degrees.', "green")
        else:
            report_status(f'Using existing: {slope_deg}..', "black")

        if not arcpy.Exists(x_sec3d_pts):
            # --------------------------------------------
            # 3D x-sections and points, point_z, slope_deg, current centre, new centre,
            # --------------------------------------------
            # Develop 3D x-sections and points
            report_status(f'Processing: 3D x-sections..', "black")
            x_sec_3d(x_sec2d, dem, slope_deg, x_sec3d, x_sec3d_pts)
            # Develop 3D x-sections points - current and new centre
            report_status(f'Processing: Current and new centres (Takes time. Watch console.)', "red")
            x_sec_current_new_centre(x_sec2d, stn_pts)
            report_status(f'Done: 3D x_sec and points.', "green")
        else:
            report_status(f'Using existing: {x_sec3d_pts}..', "black")
    # --------------------------------------------
    # CASE 4 - Level them
    # --------------------------------------------
    if option_num == 4:
        # To continue 3D x-section points must exists
        if not arcpy.Exists(x_sec3d_pts):
            report_status(f'{x_sec3d_pts} does not exist', "red")
            return None

        # Call function
        if not chk_btn_upstream_level_correction_var.get() == 0:
            do_upstream = True
            x_sec3d_levelled_pts = f'{x_sec3d}_s{slope_at}_levelled_pts_corrected'
            x_sec3d_levelled_lines = f'{x_sec3d}_s{slope_at}_levelled_lines_corrected'
            x_sec3d_levelled_bfw_poly = f'{x_sec3d}_s{slope_at}_levelled_poly_corrected'
        else:
            do_upstream = False
            x_sec3d_levelled_pts = f'{x_sec3d}_s{slope_at}_levelled_pts'
            x_sec3d_levelled_lines = f'{x_sec3d}_s{slope_at}_levelled_lines'
            x_sec3d_levelled_bfw_poly = f'{x_sec3d}_s{slope_at}_levelled_poly'

        # Check if one of the levelled outputs already exists.
        # - if exists re-run the same without updating slope_at field values
        # -     but user can update them backend and run again
        # - else run a new one by updating slope_at field values
        # -----------------------------------------------------------------------------------------

        if arcpy.Exists(x_sec3d_levelled_pts):
            report_status(f'Re-writing existing outputs. E.g {x_sec3d_levelled_pts}.', "black")
            add_field_with_a_value(x_sec3d_pts, "slope_at", "LONG", slope_at)
        else:
            report_status(f'Using afresh: {x_sec3d_pts}..', "black")
            # add these fields for the first time
            add_field_with_a_value(x_sec3d_pts, "slope_at", "LONG", slope_at)

        # Develop levelled 3D x-sections and points
        # -----------------------------------------
        report_status(f'Developing Levelled 3D x-sections and points..', "black")
        arcpy.DeleteField_management(in_table=x_sec3d_pts,
                                     drop_field="MIN_Sort_Value;MAX_Sort_Value;MAX_NewCentre")
        # --------------------------------------------
        # Step 1: Get high slope points and level
        # --------------------------------------------
        report_status(f'Processing: Points with high slopes..', "black")

        global pts_high_slopes
        pts_high_slopes = tempGDB + "\\pts_high_slopes"
        delete_temps([pts_high_slopes])

        get_pts_high_slopes()
        report_status(f'Done: Points with high slopes..{pts_high_slopes}', "black")

        report_status(f'Processing: Levelling points (Takes time. Watch console.)', "red")
        delete_temps([x_sec3d_levelled_pts])
        x_sec_level_points(pts_high_slopes, x_sec3d_levelled_pts, do_upstream)
        report_status(f'Done: Levelled points.', "green")

        # --------------------------------------------
        # Step 3: Get levelled lines
        # --------------------------------------------
        report_status(f'Processing: Levelled lines..', "black")
        delete_temps([x_sec3d_levelled_lines, x_sec3d_levelled_bfw_poly])
        arcpy.PointsToLine_management(Input_Features=x_sec3d_levelled_pts,
                                      Output_Feature_Class=x_sec3d_levelled_lines,
                                      Line_Field="x_sec_id", Sort_Field="Sort_Value", Close_Line="NO_CLOSE")
        arcpy.JoinField_management(in_data=x_sec3d_levelled_lines, in_field="x_sec_id",
                                   join_table=x_sec3d_levelled_pts, join_field="x_sec_id",
                                   fields="seg_id")
        arcpy.JoinField_management(in_data=x_sec3d_levelled_lines, in_field="x_sec_id",
                                   join_table=x_sec3d_levelled_pts,
                                   join_field="x_sec_id", fields="lvl_z")

        w_d_stats = tempGDB + "\\w_d_stats"
        arcpy.Statistics_analysis(in_table=x_sec3d_levelled_pts,
                                  out_table=w_d_stats,
                                  statistics_fields="POINT_Z MIN;POINT_Z MAX", case_field="x_sec_id")
        arcpy.AddField_management(in_table=w_d_stats, field_name="lvl_d", field_type="DOUBLE")
        arcpy.CalculateField_management(in_table=w_d_stats, field="lvl_d",
                                        expression="round ((!MAX_POINT_Z! - !MIN_POINT_Z!), 4)",
                                        expression_type="PYTHON", code_block="")

        arcpy.JoinField_management(in_data=x_sec3d_levelled_lines, in_field="x_sec_id",
                                   join_table=w_d_stats, join_field="x_sec_id", fields="lvl_d")
        arcpy.AddField_management(in_table=x_sec3d_levelled_lines, field_name="lvl_w", field_type="DOUBLE")
        arcpy.CalculateField_management(in_table=x_sec3d_levelled_lines, field="lvl_w",
                                        expression="round (!Shape_Length!, 4)", expression_type="PYTHON",
                                        code_block="")
        delete_temps([w_d_stats])
        # --------------------------------------------
        # Step 4: Get BFW polygon
        # --------------------------------------------
        report_status(f'Processing: Bankfull polygon..', "black")
        x_sec_bfw_poly(x_sec3d_levelled_lines, x_sec3d_levelled_bfw_poly)
        report_status(f'Completed the process.', "green")

    # Clean up
    delete_temps([temp_path[0]])
    enable_options()
    exit()


# -------------------------------------------------------------------------------------------------------------------
# GUI functions
# --------------------------------------------------------------------------------------------------------------------


def enable_options():
    btn_process.config(text="Process", state="normal")
    chk_btn_stnpts.config(state="normal")
    chk_btn_2D_x_secs.config(state="normal")
    chk_btn_3D_x_secs.config(state="normal")
    chk_btn_3D_x_secs_slope_lvl.config(state="normal")
    chk_btn_upstream_level_correction.config(state="normal")
    entry_mwstr_path.config(state="normal")
    entry_dem.config(state="normal")
    entry_interval.config(state="normal")
    width_menu.config(state="normal")
    entry_slope.config(state="normal")
    entry_out_loc.config(state="normal")


def disable_optons():
    btn_process.config(text="Processing ...", state="disabled")
    chk_btn_stnpts.config(state="disable")
    chk_btn_2D_x_secs.config(state="disable")
    chk_btn_3D_x_secs.config(state="disable")
    chk_btn_3D_x_secs_slope_lvl.config(state="disable")
    chk_btn_upstream_level_correction.config(state="disable")
    entry_mwstr_path.config(state="disabled")
    entry_dem.config(state="disabled")
    entry_interval.config(state="disabled")
    width_menu.config(state="disabled")
    entry_slope.config(state="disabled")
    entry_out_loc.config(state="disabled")


def report_status(statement, colour):
    print(statement)
    lbl_status.config(text=statement, fg=colour)
    root.update()


def validate_entries(mwstr, dem, out_loc, interval, slope_at):
    lbl_status.config(text=default_status, fg="black")

    entry_mwstr_path.config(fg="black")
    entry_dem.config(fg="black")
    entry_out_loc.config(fg="black")
    entry_interval.config(fg="black")
    entry_slope.config(fg="black")

    # Validate input - stream layer
    if not arcpy.Exists(mwstr):
        lbl_status.config(text=f'Error: {mwstr} does not exist', fg="red")
        entry_mwstr_path.config(fg="red")
        return False

    # Validate input - dem layer
    if not arcpy.Exists(dem):
        lbl_status.config(text=f'Error: {dem} does not exist', fg="red")
        entry_dem.config(fg="red")
        return False

    # Validate output location
    if not arcpy.Exists(out_loc):
        lbl_status.config(text=f'Error: {out_loc} does not exist', fg="red")
        entry_out_loc.config(fg="red")
        return False

    # Validate interval
    try:
        int(interval)
        if int(interval) > 1000 or int(interval) < 5:
            lbl_status.config(text="Error: Interval must be between 5 to  1000.", fg="red")
            entry_interval.config(fg="red")
            return False
    except ValueError:
        lbl_status.config(text="Error: Interval must be a number.", fg="red")
        entry_interval.config(fg="red")
        return False

    # Validate slope threshold
    try:
        int(slope_at)
        if int(slope_at) > 15 or int(slope_at) < 5:
            lbl_status.config(text="Error: Slope must be between 5 to 15.", fg="red")
            entry_slope.config(fg="red")
            return False
    except ValueError:
        lbl_status.config(text="Error: Slope must be a number.", fg="red")
        entry_slope.config(fg="red")
        return False

    # by default return true
    return True


# -------------------------------------------------------------------------------------------------------------------
# station point functions
# --------------------------------------------------------------------------------------------------------------------


def station_points(mwstr_dis, station_points, station_dist, station_points_sort_value):
    temp_list = [station_points]
    delete_temps(temp_list)
    # ---Develop station_points_25m-----------------------------------------------------------------------------------
    arcpy.GeneratePointsAlongLines_management(mwstr_dis, station_points, "DISTANCE", station_dist, "", "")
    add_field_with_a_value(station_points, "x_sec_id", "LONG", '!OBJECTID!')
    add_field_with_a_value(station_points, "SortField", "SHORT", station_points_sort_value)


# -------------------------------------------------------------------------------------------------------------------
# 2D x-section functions
# --------------------------------------------------------------------------------------------------------------------


def x_sec_2D(mwstr_dis, station_points, station_points_sort_value, buffers_list, out_transacts):

    # Temp Datasets
    stn_pts = tempGDB + "\\stn_pts"
    temp_list = [out_transacts, stn_pts]
    delete_temps(temp_list)

    # ---------------------------------------------------------------------------------------------------------------
    # ---Run a for loop for each item in buffers list ----------------------------------------------------------------
    merge_string = ""
    station_points_25m_l = station_points
    station_points_25m_r = station_points
    i = 0

    for item in buffers_list:
        distance = str(item) + " Meters"
        distance_to_erase = str((item - 0.5)) + " Meters"

        # Buffer erase, left and right
        buf_erase = tempGDB + "\\buf_erase"
        buf_l = tempGDB + "\\buf_l"
        buf_r = tempGDB + "\\buf_r"

        arcpy.Buffer_analysis(mwstr_dis, buf_erase, distance_to_erase, "FULL", "ROUND", "ALL", "", "PLANAR")
        arcpy.Buffer_analysis(mwstr_dis, buf_l, distance, "LEFT", "FLAT", "ALL", "", "PLANAR")
        arcpy.Buffer_analysis(mwstr_dis, buf_r, distance, "RIGHT", "FLAT", "ALL", "", "PLANAR")

        # Develop left and right lines by erasing middle erase buffer
        buf_l_line = tempGDB + "\\buf_l_line"
        buf_r_line = tempGDB + "\\buf_r_line"
        l_line = tempGDB + "\\l_line"
        r_line = tempGDB + "\\r_line"

        arcpy.PolygonToLine_management(buf_l, buf_l_line, "IDENTIFY_NEIGHBORS")
        arcpy.Erase_analysis(buf_l_line, buf_erase, l_line, "")
        arcpy.PolygonToLine_management(buf_r, buf_r_line, "IDENTIFY_NEIGHBORS")
        arcpy.Erase_analysis(buf_r_line, buf_erase, r_line, "")

        # Process: Left -----------------------------------------------------------------------------------------------
        arcpy.Select_analysis(station_points_25m_l, stn_pts, "")
        arcpy.Near_analysis(stn_pts, l_line, "", "LOCATION", "NO_ANGLE", "PLANAR")
        arcpy.MakeXYEventLayer_management(stn_pts, "NEAR_X", "NEAR_Y", "stn_pts_layer", proj_gda94z55_def, "")

        pts_l_item = tempGDB + "\\pts_l_" + str(item)

        arcpy.Select_analysis("stn_pts_layer", pts_l_item, "")
        arcpy.DeleteField_management(in_table=pts_l_item, drop_field="ORIG_FID;NEAR_FID;NEAR_DIST;NEAR_X;NEAR_Y")

        sort_value_l = len(buffers_list) - i

        arcpy.CalculateField_management(pts_l_item, "SortField", sort_value_l)

        station_points_25m_l = pts_l_item

        # delete outputs if the already exist.
        temp_list = [buf_l, buf_l_line, "stn_pts_layer", stn_pts, l_line]
        delete_temps(temp_list)

        # Process: Right ----------------------------------------------------------------------------------------------
        arcpy.Select_analysis(station_points_25m_r, stn_pts, "")
        arcpy.Near_analysis(stn_pts, r_line, "", "LOCATION", "NO_ANGLE", "PLANAR")
        arcpy.MakeXYEventLayer_management(stn_pts, "NEAR_X", "NEAR_Y", "stn_pts_layer", proj_gda94z55_def, "")

        pts_r_item = tempGDB + "\\pts_r_" + str(item)

        arcpy.Select_analysis("stn_pts_layer", pts_r_item, "")
        arcpy.DeleteField_management(in_table=pts_r_item, drop_field="ORIG_FID;NEAR_FID;NEAR_DIST;NEAR_X;NEAR_Y")

        sort_value_r = station_points_sort_value + 1 + i

        arcpy.CalculateField_management(pts_r_item, "SortField", sort_value_r)

        station_points_25m_r = pts_r_item

        # delete outputs if the already exist.
        temp_list = [buf_r, buf_r_line, buf_erase, "stn_pts_layer", stn_pts, r_line]
        delete_temps(temp_list)

        i += 1

        # Construct a merge string
        merge_string += ";" + pts_l_item + ";" + pts_r_item
        print("Processed: " + pts_l_item + " and " + pts_r_item)

    # Merge files-----------------------------------------------------------------------------------------------------
    pts_all = tempGDB + "\\pts_all"

    merge_string = merge_string[1:] + ";" + station_points
    arcpy.Merge_management(merge_string, pts_all, "")
    print("Processed: Merged points " + pts_all)

    # Process: Points To Transacts -----------------------------------------------------------------------------------
    arcpy.PointsToLine_management(pts_all, out_transacts, "x_sec_id", "SortField", "NO_CLOSE")

    # Delete buffer files
    delete_list = merge_string.split(";")
    delete_temps(delete_list)
    temp_list = [pts_all]
    delete_temps(temp_list)

    print("2D Cross section process completed.")


# -------------------------------------------------------------------------------------------------------------------
# 3D x-section functions
# --------------------------------------------------------------------------------------------------------------------


def get_raster_value_for_points(pts_shp, dem, elev_field):
    extract_pts = tempGDB + "\\extract_pts"
    delete_temps([extract_pts])
    if not has_fld(pts_shp, elev_field):
        arcpy.AddField_management(pts_shp, elev_field, "DOUBLE")

    if pts_shp.endswith('.shp'):
        fldvalue = '!FID! + 1'
    else:
        fldvalue = '!OBJECTID!'

    add_field_with_a_value(pts_shp, "UNQID", "LONG", fldvalue)
    # Process: Extract Values
    arcpy.gp.ExtractValuesToPoints_sa(pts_shp, dem, extract_pts, "NONE", "VALUE_ONLY")
    # arcpy.gp.ExtractValuesToPoints_sa(pts_shp, dem, extract_pts, "INTERPOLATE", "VALUE_ONLY")
    # Process: Join Field
    arcpy.JoinField_management(pts_shp, "UNQID", extract_pts, "UNQID", "RASTERVALU")
    # Process: Calculate Field
    arcpy.CalculateField_management(pts_shp, elev_field, '!RASTERVALU!', "PYTHON_9.3", "")
    # Process: Delete Field
    arcpy.DeleteField_management(pts_shp, "RASTERVALU")

    # clean up
    delete_temps([extract_pts])


def x_sec_current_new_centre(x_sec2d, stn_pts):

    # due to lines intersect this needs to be done for each cross section
    # loop through each x_sec_id to get new_centre ------------------------------------------------------------

    # Add fields CurCentre and NewCentre
    add_field_with_a_value(x_sec3d_pts, "CurCentre", "SHORT", "None")
    add_field_with_a_value(x_sec3d_pts, "NewCentre", "SHORT", 'None')

    # MakeFeatureLayer and delete at the end
    arcpy.MakeFeatureLayer_management(in_features=x_sec3d_pts, out_layer="x_sec3d_pts_lyr")

    # Use x_sec2d to loop through for each x_sec_id - cursor1
    # ----------------------------------------------------
    cursor1 = arcpy.SearchCursor(x_sec2d, ['x_sec_id'])
    for cursor1_row in cursor1:
        x_sec_id = cursor1_row.getValue("x_sec_id")
        # x_sec_id = 1706

        stn_pts_sel = tempGDB + "\\stn_pts_sel"
        arcpy.Select_analysis(stn_pts, stn_pts_sel, f'x_sec_id = {x_sec_id}')

        # Getting current centre using select by location stn_pts_sel
        # -----------------------------------------------------------------
        print(f'Getting current centre for x_sec_id = {x_sec_id}')

        arcpy.SelectLayerByAttribute_management(in_layer_or_view="x_sec3d_pts_lyr",
                                                selection_type="NEW_SELECTION",
                                                where_clause=f'x_sec_id = {x_sec_id}')
        arcpy.SelectLayerByLocation_management(in_layer="x_sec3d_pts_lyr", overlap_type="INTERSECT",
                                               select_features=stn_pts_sel, search_distance="0.2 Meters",
                                               selection_type="SUBSET_SELECTION",
                                               invert_spatial_relationship="NOT_INVERT")
        arcpy.CalculateField_management("x_sec3d_pts_lyr", "CurCentre", '!Sort_Value!', "PYTHON_9.3", "")
        arcpy.SelectLayerByAttribute_management("x_sec3d_pts_lyr", "CLEAR_SELECTION")

        # Getting new centre
        # -------------------------------------------------------------------------
        # 1. Select x_sec3d_pts within 5 meters of stn_pts_sel of this x_sec_id and
        # get their POINT_Z MIN as min_z
        # -------------------------------------------------------------------------------
        print(f'Getting new centre for x_sec_id = {x_sec_id}')
        arcpy.SelectLayerByAttribute_management(in_layer_or_view="x_sec3d_pts_lyr",
                                                selection_type="NEW_SELECTION",
                                                where_clause=f'x_sec_id = {x_sec_id}')
        arcpy.SelectLayerByLocation_management(in_layer="x_sec3d_pts_lyr", overlap_type="INTERSECT",
                                               select_features=stn_pts_sel, search_distance="5 Meters",
                                               selection_type="SUBSET_SELECTION",
                                               invert_spatial_relationship="NOT_INVERT")
        x_sec3d_pts_sel = tempGDB + "\\x_sec3d_pts_sel"
        arcpy.Select_analysis("x_sec3d_pts_lyr", x_sec3d_pts_sel, "")
        arcpy.SelectLayerByAttribute_management("x_sec3d_pts_lyr", "CLEAR_SELECTION")
        # MakeFeatureLayer and delete at the end
        arcpy.MakeFeatureLayer_management(in_features=x_sec3d_pts_sel, out_layer="x_sec3d_pts_sel_lyr")

        tbl_x_sec_min_z = tempGDB + "\\tbl_x_sec_min_z"
        arcpy.Statistics_analysis(in_table=x_sec3d_pts_sel, out_table=tbl_x_sec_min_z,
                                  statistics_fields="POINT_Z MIN", case_field="x_sec_id")

        cursor2 = arcpy.SearchCursor(tbl_x_sec_min_z, ['MIN_POINT_Z'])
        for cursor2_row in cursor2:
            min_z = cursor2_row.getValue("MIN_POINT_Z") + 0.01
            # -------------------------------------------------------------------------
            # 2. Select records where POINT_Z <= min_z
            # --------------------------------------------------------------------------
            statement1 = f'x_sec_id = {x_sec_id} AND POINT_Z <= {min_z}'
            print(statement1)
            arcpy.SelectLayerByAttribute_management(in_layer_or_view="x_sec3d_pts_sel_lyr",
                                                    selection_type="NEW_SELECTION",
                                                    where_clause=statement1)
            # -------------------------------------------------------------------------
            # 3. There will be more than on record where POINT_Z <= round({min_z}, 4
            # Collect them and get their min and max sort_values for this x_sec_id.
            # --------------------------------------------------------------------------
            tbl_x_sec_sort_min_max = tempGDB + "\\tbl_x_sec_sort_min_max"
            arcpy.Statistics_analysis(in_table="x_sec3d_pts_sel_lyr", out_table=tbl_x_sec_sort_min_max,
                                      statistics_fields="Sort_Value MIN;Sort_Value MAX", case_field="x_sec_id")
            arcpy.SelectLayerByAttribute_management(in_layer_or_view="x_sec3d_pts_sel_lyr",
                                                    selection_type="CLEAR_SELECTION", where_clause="")
            delete_temps([x_sec3d_pts_sel, "x_sec3d_pts_sel_lyr"])
            # -------------------------------------------------------------------------
            # 4. Get new value using below logic and set the new centre
            # --------------------------------------------------------------------------
            cursor3 = arcpy.SearchCursor(tbl_x_sec_sort_min_max, ['FREQUENCY', 'MIN_Sort_Value', 'MAX_Sort_Value'])
            for cursor3_row in cursor3:
                if cursor3_row.getValue("FREQUENCY") in (1, 2):
                    value_new = int(cursor3_row.getValue("MIN_Sort_Value"))
                else:
                    value_new = int(cursor3_row.getValue("MIN_Sort_Value") + (cursor3_row.getValue("FREQUENCY") // 2))

                statement2 = f'x_sec_id = {x_sec_id} AND Sort_Value = {value_new}'

                arcpy.SelectLayerByAttribute_management(in_layer_or_view="x_sec3d_pts_lyr",
                                                        selection_type="NEW_SELECTION", where_clause=statement2)
                arcpy.CalculateField_management(in_table="x_sec3d_pts_lyr", field="NewCentre",
                                                expression=value_new, expression_type="PYTHON", code_block="")
                arcpy.SelectLayerByAttribute_management(in_layer_or_view="x_sec3d_pts_lyr",
                                                        selection_type="CLEAR_SELECTION", where_clause="")
                print(f'x_sec_id = {x_sec_id} AND New Centre at = {value_new}')
            # exit()
            # Delete 3rd level temps
            delete_temps([tbl_x_sec_sort_min_max])
        # Delete 2nd level temps
        delete_temps([stn_pts_sel, tbl_x_sec_min_z, x_sec3d_pts_sel])
    # Delete 1st level temps
    delete_temps(["x_sec3d_pts_lyr"])


def x_sec_3d(transacts_2d, dem, slope_deg, transacts3d, x_sec3d_pts):

    id_min = tempGDB + "\\id_min"

    delete_list = [transacts3d, id_min]
    delete_temps(delete_list)

    print(f'Get 3D transacts and convert {transacts3d} vertices to points - {x_sec3d_pts}.')  # ---------------
    arcpy.InterpolateShape_3d(in_surface=dem, in_feature_class=transacts_2d, out_feature_class=transacts3d,
                              sample_distance="1", z_factor="1", method="BILINEAR",
                              vertices_only="DENSIFY", pyramid_level_resolution="0")
    arcpy.FeatureVerticesToPoints_management(in_features=transacts3d, out_feature_class=x_sec3d_pts,
                                             point_location="ALL")

    print(f'Add XYZ')  # -----------------------------------------------------------------------------------------
    arcpy.AddGeometryAttributes_management(Input_Features=x_sec3d_pts, Geometry_Properties="POINT_X_Y_Z_M",
                                           Length_Unit="", Area_Unit="", Coordinate_System="")
    # arcpy.AddXY_management(in_features=x_sec3d_pts)

    print(f'Add field for sorting and get sorted values for each transact.')  # ----------------------------------
    arcpy.AddField_management(in_table=x_sec3d_pts, field_name="Sort_Value", field_type="LONG")
    arcpy.Statistics_analysis(x_sec3d_pts, id_min, "OBJECTID MIN", "x_sec_id")
    arcpy.CalculateField_management(in_table=id_min, field="MIN_OBJECTID", expression="!MIN_OBJECTID! - 1",
                                    expression_type="PYTHON_9.3", code_block="")
    arcpy.JoinField_management(in_data=x_sec3d_pts, in_field="x_sec_id", join_table=id_min,
                               join_field="x_sec_id", fields="MIN_OBJECTID")
    arcpy.CalculateField_management(in_table=x_sec3d_pts, field="Sort_Value",
                                    expression="!OBJECTID! - !MIN_OBJECTID!", expression_type="PYTHON_9.3",
                                    code_block="")
    arcpy.DeleteField_management(in_table=x_sec3d_pts, drop_field="ORIG_FID;MIN_OBJECTID")

    print(f'Get slope in degree for {x_sec3d_pts}.')  # ------------------------------------------------------
    get_raster_value_for_points(x_sec3d_pts, dem=slope_deg, elev_field="slope_deg")

    delete_list = [id_min]
    delete_temps(delete_list)

    print("Process completed: See Outputs - " + transacts3d + " and " + x_sec3d_pts)  # -----------------------


# -------------------------------------------------------------------------------------------------------------------
# Levelling functions
# --------------------------------------------------------------------------------------------------------------------


def apply_linear_regression(tbl_x_id_lvl_z_seg_id, pts_high_slopes):
    """
    1. Get list without general outliers
    2. Model linear regression without outliers
    3. Get predicted and residuals using the Model that is without outliers
    4. Adjust values

    :param tbl_x_id_lvl_z_seg_id:
    :param pts_high_slopes:
    :return:
    """
    # this layer (pts_high_slopes_lyr) "lvl_z" will be updated
    # delete_temps(["pts_high_slopes_lyr"])
    # arcpy.MakeFeatureLayer_management(in_features=pts_high_slopes, out_layer="pts_high_slopes_lyr")

    # This temporary table (tbl_x_id_lvl_z_seg_id) will be used to get updated lvl_z values)
    # develop two lists
    values_x = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_lvl_z_seg_id, 'x_sec_id')]
    list_x_org = list(values_x)
    values_y = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_lvl_z_seg_id, 'MAX_lvl_z')]
    list_y_org = list(values_y)
    delete_temps([tbl_x_id_lvl_z_seg_id]) # this temp table no longer required.
    print(list_x_org)
    print(list_y_org)

    x_org = np.array(list_x_org).reshape((-1, 1))
    y_org = np.array(list_y_org)

    if len(list_x_org) < 5:  # if number of observations < 5
        print("No. of Observations < 5")
        return None

    # 1. Get list without general outliers
    # ------------------------------
    list_x_org2, list_y_org2 = list_without_outliers(list_x_org, list_y_org)
    if len(list_x_org2) == len(list_x_org):  # nothing has been removed.
        print(f'No outliers.')
        return None

    # 2. Model linear regression without outliers
    # ------------------------------------------
    x2 = np.array(list_x_org2).reshape((-1, 1))
    y2 = np.array(list_y_org2)

    model_no_outliers = LinearRegression().fit(x2, y2)  # this is developed using the lists that has NO outliers.
    r_sq = round(model_no_outliers.score(x2, y2), 2)
    m_slope = model_no_outliers.coef_
    print('R2 after removal of Outlier:', r_sq)
    # print('Intercept:', round(model_no_outliers.intercept_, 2))
    print('Slope:', m_slope)

    if m_slope > 0:
        print(f'Positive Slope.')
        return None

    # 3. Get predicted and residuals using the Model that is without outliers
    # -----------------------------------------------------

    y_org_pred = model_no_outliers.predict(x_org)
    list_y_org_pred = y_org_pred.tolist()  # make a list of predicted values for the original values
    y_diff = y_org - y_org_pred
    print(f'Residuals = {y_diff}')

    # # # Plot outputs
    # plt.scatter(x_org, y_org, color="black")
    # plt.plot(x_org, y_org_pred, color="blue", linewidth=3)
    # plt.xticks(())
    # plt.yticks(())
    # plt.show()

    # 4. Adjust values
    # -----------------------------------------------------------------------
    i = 0
    for value in y_diff:
        if value < -1 or value > 1:  # if the difference is between +/- 1
            y_org[i] = y_org_pred[i]
            y_new = list_y_org_pred[i]
            print(f'Re-adjusted: {x_org[i]}, {y_org[i]}')
            calc_lvl_for_a_x_sec(list_x_org[i], y_new)

            expression = f'x_sec_id = {list_x_org[i]} and POINT_Z <= {y_new}'
            flag_to_delete_features_using_expression(pts_high_slopes, expression, 0)
        i += 1


def calc_lvl_for_a_x_sec(x_sec_id, lvl_z):
    expression = f'x_sec_id = {str(x_sec_id)}'
    # print(expression)
    arcpy.MakeFeatureLayer_management(in_features=pts_high_slopes,
                                      out_layer="pts_high_slopes_lyr")
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_lyr",
                                            selection_type="NEW_SELECTION", where_clause=expression)
    arcpy.CalculateField_management(in_table="pts_high_slopes_lyr", field="lvl_z",
                                    expression=lvl_z, expression_type="PYTHON",
                                    code_block="")
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_lyr",
                                            selection_type="CLEAR_SELECTION", where_clause="")
    delete_temps(["pts_high_slopes_lyr"])


def get_pts_high_slopes():
    """
    1. get pts_high_slopes1 where (slope_deg >= slope_at) OR  (NewCentre is not NULL) OR (CurCentre is not NULL)
    2. get min and max sort values for pts_high_slopes1 and join them to x_sec3d_pts
    3.Select pts_high_slopes from x_sec3d_pts using (slope_deg >= slope_at) OR (NewCentre is not NULL) OR
    (CurCentre is not NULL) OR (Sort_Value = MIN_Sort_Value - 1) OR (Sort_Value = MAX_Sort_Value + 1)

    :param x_sec3d_pts:
    :param pts_high_slopes:
    :return:
    """

    # 1. get pts_high_slopes1 where (slope_deg >= slope_at) OR  (NewCentre is not NULL) OR (CurCentre is not NULL)
    # -------------------------------------------------------------------------------------------------------------
    pts_high_slopes1 = tempGDB + "\\pts_high_slopes1"
    delete_temps([pts_high_slopes1])
    select_statement1 = "(slope_deg >= slope_at) OR (NewCentre is not NULL) OR (CurCentre is not NULL)"
    arcpy.Select_analysis(in_features=x_sec3d_pts, out_feature_class=pts_high_slopes1,
                          where_clause=select_statement1)

    # 2. get min and max sort values for pts_high_slopes1 and join them to x_sec3d_pts
    # -------------------------------------------------------------------------------------------------------------
    tbl_x_id_sort_start_ends = tempGDB + "//tbl_x_id_sort_start_ends"
    delete_temps([tbl_x_id_sort_start_ends])

    arcpy.Statistics_analysis(in_table=pts_high_slopes1, out_table=tbl_x_id_sort_start_ends,
                              statistics_fields="Sort_Value MIN;Sort_Value MAX", case_field="x_sec_id")
    arcpy.JoinField_management(in_data=x_sec3d_pts, in_field="x_sec_id",
                               join_table=tbl_x_id_sort_start_ends, join_field="x_sec_id",
                               fields="MIN_Sort_Value;MAX_Sort_Value")

    # 3.Select pts_high_slopes from x_sec3d_pts using (slope_deg >= slope_at) OR (NewCentre is not NULL) OR
    # (CurCentre is not NULL) OR (Sort_Value = MIN_Sort_Value - 1) OR (Sort_Value = MAX_Sort_Value + 1)"
    # -------------------------------------------------------------------------------------------------------------
    select_statement = "(slope_deg >= slope_at) OR (NewCentre is not NULL) OR (CurCentre is not NULL) OR " \
                       "(Sort_Value = MIN_Sort_Value - 1) OR (Sort_Value = MAX_Sort_Value + 1)"
    arcpy.Select_analysis(in_features=x_sec3d_pts, out_feature_class=pts_high_slopes, where_clause=select_statement)

    arcpy.DeleteField_management(in_table=x_sec3d_pts, drop_field="MIN_Sort_Value;MAX_Sort_Value")
    arcpy.DeleteField_management(in_table=pts_high_slopes, drop_field="MIN_Sort_Value;MAX_Sort_Value")

    delete_temps([pts_high_slopes1, tbl_x_id_sort_start_ends])


def list_without_outliers(list_x_org, list_y_org):
    # find general outliers
    # ------------------------------
    list_x_org2 = []
    list_y_org2 = []
    i = 0
    len_x = len(list_x_org) - 1
    for x_value in list_x_org:
        cur_x = list_x_org[i]
        cur_y = list_y_org[i]
        if i > 0:
            pre_y = list_y_org[i - 1]
        else:
            pre_y = cur_y

        if (i + 1) <= len_x:
            next_y = list_y_org[i + 1]
        else:
            next_y = cur_y

        # logic
        # print(f'{pre_y}, {cur_y}, {next_y}')
        if cur_y < (pre_y - 3) or cur_y < (next_y - 3):  # outlier
            print(f'Outlier value: {cur_y}')
        else:
            list_x_org2.append(cur_x)
            list_y_org2.append(cur_y)
        # increase i
        i += 1

    return list_x_org2, list_y_org2


def lvl_elev(list_left_point_z, list_right_point_z):
    if max(list_left_point_z) < max(list_right_point_z):
        lvl_z = max(list_left_point_z)
    else:
        lvl_z = max(list_right_point_z)
    return lvl_z


def slope_gap_adjustment(list_sort_values, list_point_z):
    gap_found = 0
    if len(list_sort_values) < 5:
        return list_sort_values, list_point_z, 0
    else:
        gap_adjusted_list_sort_values = []
        gap_adjusted_list_point_z = []
        gap = 3

        i = 0
        for sv in list_sort_values:
            cur_sv = list_sort_values[i]
            cur_pt_z = list_point_z[i]
            # print(cur_sv)
            if i < 3: # let the first two point go
                gap_adjusted_list_sort_values.append(cur_sv)
                gap_adjusted_list_point_z.append(cur_pt_z)
            else:
                sv_gap = cur_sv - list_sort_values[i - 1]
                if sv_gap < 0:
                    sv_gap = - sv_gap
                # print(sv_gap)
                if sv_gap <= gap:
                    gap_adjusted_list_sort_values.append(cur_sv)
                    gap_adjusted_list_point_z.append(cur_pt_z)
                else:
                    print(f'Slope discontinuity found.')
                    gap_found = 1
                    break
            i += 1
    return gap_adjusted_list_sort_values, gap_adjusted_list_point_z, gap_found


def x_sec_level_points(pts_high_slopes, x_sec3d_levelled_pts, do_upstream):

    # Step 1 - Using pts_high_slopes layer to get and join MIN_Sort_Value;MAX_Sort_Value;MAX_NewCentre
    # -----------------------------------------------------------------------------------------------
    tbl_x_id_new_centre_sort_start_ends = x_sec_level_points_tbl_x_id_new_centre_sort_start_ends()

    # Step 2: Setup lists
    # ------------------------------------------------------------------------------------------------
    list_x_sec_id, list_MIN_Sort_Value, list_MAX_Sort_Value, list_NewCentre = \
        x_sec_level_points_list_x_sec_id_MIN_MAX_Sort_Value_NewCentre(tbl_x_id_new_centre_sort_start_ends)

    # For each x_sec_id
    # -----------------------------------------------------------------------------------------------
    """
    a. Get MIN_Sort_Value, MAX_Sort_Value and NewCentre
    b. Select pts_high_slopes_for_a_x_sec & get list_sort_values and list_POINT_Z
    c. Separate 4 lists - list_left_sort_values, list_left_point_z, list_right_sort_values, list_right_point_z
    d. Call the function x_sec_level_points_both_sides to get levelled list. 
    """
    i = 0
    for x_sec_id in list_x_sec_id:
        x_sec_id = list_x_sec_id[i]

        # a. Get MIN_Sort_Value, MAX_Sort_Value and NewCentre
        # ------------------------------------------------------
        print(f'-----------------------------------------------')
        print(f'x_sec_id = {x_sec_id}')
        print(f'-----------------------------------------------')
        MIN_Sort_Value = int(list_MIN_Sort_Value[i])
        MAX_Sort_Value = int(list_MAX_Sort_Value[i])
        NewCentre = int(list_NewCentre[i])

        # b. Select pts_high_slopes_for_a_x_sec & get list_sort_values and list_POINT_Z
        # -------------------------------------------------------------------------------
        expression = "x_sec_id = " + str(x_sec_id)
        list_sort_values, list_POINT_Z = get_lists_for_sv_and_z_for_xsec_id(x_sec_id, expression, None)

        # c. Separate 4 lists - list_left_sort_values, list_left_point_z, list_right_sort_values, list_right_point_z
        # ---------------------------------------------------------
        index_new_centre = list_sort_values.index(NewCentre)
        index_MIN_Sort_Value = list_sort_values.index(MIN_Sort_Value)
        index_MAX_Sort_Value = list_sort_values.index(MAX_Sort_Value)
        # Left values
        list_left_sort_values = list_sort_values[index_MIN_Sort_Value:index_new_centre+1]
        list_left_sort_values.reverse()
        list_left_point_z = list_POINT_Z[index_MIN_Sort_Value:index_new_centre+1]
        list_left_point_z.reverse()
        # Right values
        list_right_sort_values = list_sort_values[index_new_centre:index_MAX_Sort_Value+1]
        list_right_point_z = list_POINT_Z[index_new_centre:index_MAX_Sort_Value+1]
        print(f'original left sort values = {list_left_sort_values}')
        print(f'original left point_z = {list_left_point_z}')
        print(f'original right sort values = {list_right_sort_values}')
        print(f'original right point_z = {list_right_point_z}')

        # d. Call the function x_sec_level_points_both_sides to get levelled list.
        # ----------------------------------------------------------------------------------------
        if len(list_left_sort_values) <= 2 or len(list_right_sort_values) <= 2:
            print(f'One of the side is short. This x_sec_id = {x_sec_id} is ignored.')
            expression = f'x_sec_id = {x_sec_id}'
            delete_features_using_expression(pts_high_slopes, expression)
        else:
            x_sec_level_points_both_sides(x_sec_id, list_left_sort_values, list_left_point_z,
                                                  list_right_sort_values, list_right_point_z, pts_high_slopes)
        # continue loop
        i += 1

    # --------------------------------------------------------------------------------------------------------
    # Step 6 - Apply linear regression on data to fine tune outliers
    # -------------------------------------------------------------------------------------------------------
    if do_upstream:
        # export a unique table for each
        tbl_x_id_seg_id_lvl_z = tempGDB + "\\tbl_x_id_seg_id_lvl_z"
        tbl_x_id_lvl_z_for_selected_reg = tempGDB + "\\tbl_x_id_lvl_z_for_selected_reg"
        delete_temps([tbl_x_id_seg_id_lvl_z])

        arcpy.Statistics_analysis(in_table=pts_high_slopes, out_table=tbl_x_id_seg_id_lvl_z,
                                  statistics_fields="seg_id MIN;lvl_z MAX", case_field="x_sec_id")
        # Set unique reg_id for each 10 points of a segment
        add_field_with_a_value(tbl_x_id_seg_id_lvl_z, "reg_id", "LONG", "None")

        # get list of seg_id
        values = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_seg_id_lvl_z, 'MIN_seg_id')]
        list_seg_ids = set(values)

        for seg_id in list_seg_ids:
            cur_seg_id = int(seg_id)
            # print(cur_seg_id)
            expression = arcpy.AddFieldDelimiters(tbl_x_id_seg_id_lvl_z, "MIN_seg_id") + f' = {cur_seg_id}'
            with arcpy.da.UpdateCursor(tbl_x_id_seg_id_lvl_z, ["x_sec_id", "reg_id"],
                                       where_clause=expression) as cursor_tbl:
                i = 1
                j = 1
                for row_tbl in cursor_tbl:
                    x_sec_id = row_tbl[0]
                    reg_id = int(f'{cur_seg_id}{j}')
                    row_tbl[1] = reg_id
                    # print(f'x_sec_id = {x_sec_id}, reg_id = {reg_id}')
                    cursor_tbl.updateRow(row_tbl)
                    i += 1
                    if i > 10:  # 10 points only
                        i = 1  # set to look for next 20 points
                        j += 1  # set next reg_id

        # get list of reg_id
        values_reg_ids = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_seg_id_lvl_z, 'reg_id')]
        list_reg_ids = set(values_reg_ids)
        list_reg_ids = sorted(list_reg_ids)
        # -----------------------------------------------------------
        for reg_id in list_reg_ids:
            cur_reg_id = int(reg_id)
            print(f'-----------------------------')
            print(f'Batch list id: = {cur_reg_id}')
            print(f'-----------------------------')
            delete_temps([tbl_x_id_lvl_z_for_selected_reg])
            arcpy.TableSelect_analysis(in_table=tbl_x_id_seg_id_lvl_z, out_table=tbl_x_id_lvl_z_for_selected_reg,
                                       where_clause=f'reg_id = {cur_reg_id}')
            # apply linear regression on data to fine tune outliers
            apply_linear_regression(tbl_x_id_lvl_z_for_selected_reg, pts_high_slopes)

    # Step 7: delete flag_delete = 1 and recalculate lvl_z for final points after deletion
    # ---------------------------------------------------------
    expression = f'flag_delete = 1'
    delete_features_using_expression(pts_high_slopes, expression)

    # Step 8: gather final bounds and the outputs ----------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------
    tbl_new_start_ends = tempGDB + "//tbl_new_start_ends"
    arcpy.Statistics_analysis(in_table=pts_high_slopes, out_table=tbl_new_start_ends,
                              statistics_fields="Sort_Value MIN;Sort_Value MAX", case_field="x_sec_id")
    arcpy.JoinField_management(in_data=x_sec3d_pts, in_field="x_sec_id", join_table=tbl_new_start_ends,
                               join_field="x_sec_id", fields="MIN_Sort_Value;MAX_Sort_Value")

    # Export newly trimmed transacts --------------------------------------------------------------------
    arcpy.Select_analysis(in_features=x_sec3d_pts, out_feature_class=x_sec3d_levelled_pts,
                          where_clause="Sort_Value >= MIN_Sort_Value AND Sort_Value <= MAX_Sort_Value")
    arcpy.DeleteField_management(in_table=x_sec3d_pts, drop_field="MIN_Sort_Value;MAX_Sort_Value")
    arcpy.DeleteField_management(in_table=x_sec3d_levelled_pts,
                                 drop_field="POINT_X;POINT_Y;UNQID;MIN_Sort_Value;MAX_Sort_Value")

    tbl_x_sec_id_lvl_z = tempGDB + "//tbl_x_sec_id_lvl_z"
    delete_temps([tbl_x_sec_id_lvl_z])
    arcpy.Statistics_analysis(in_table=x_sec3d_levelled_pts, out_table=tbl_x_sec_id_lvl_z,
                              statistics_fields="POINT_Z MAX", case_field="x_sec_id")
    add_field_with_a_value(tbl_x_sec_id_lvl_z, "lvl_z", "DOUBLE", '!MAX_POINT_Z!')

    arcpy.JoinField_management(in_data=x_sec3d_levelled_pts, in_field="x_sec_id", join_table=tbl_x_sec_id_lvl_z,
                               join_field="x_sec_id", fields="lvl_z")

    delete_temps([tbl_x_sec_id_lvl_z])

    print("Process Completed: " + x_sec3d_levelled_pts)


def x_sec_level_points_both_sides(x_sec_id, list_left_sort_values, list_left_point_z,
                                          list_right_sort_values, list_right_point_z, pts_high_slopes):
    # if x_sec_id in (249, 637):
    #     print("249, 637")

    print(f'')
    print(f'Step 1: Level based on maximum elevation of sides..')
    print(f'------')
    lvl_z = lvl_elev(list_left_point_z, list_right_point_z)
    calc_lvl_for_a_x_sec(x_sec_id, lvl_z)
    print(f'Starting lvl_z = {lvl_z}')
    list_left_sort_values_trim1, list_left_point_z_trim1 = trim_list_using_max_elev(lvl_z, list_left_sort_values,
                                                                                list_left_point_z)
    list_right_sort_values_trim1, list_right_point_z_trim1 = trim_list_using_max_elev(lvl_z, list_right_sort_values,
                                                                                  list_right_point_z)

    # delete one side banks, otherwise move on.
    if len(list_left_sort_values_trim1) <= 1 or len(list_right_sort_values_trim1) <= 1:  # if a list is empty
        print(f'One of the list is empty. This x_sec_id = {x_sec_id} is ignored.')
        expression = f'x_sec_id = {x_sec_id}'
        delete_features_using_expression(pts_high_slopes, expression)
        return None
    elif (len(list_left_sort_values_trim1) == len(list_left_sort_values)) and \
            (len(list_right_sort_values_trim1) == len(list_right_sort_values)):
        print(f'No changes to the list.')
    else:
        calc_lvl_for_a_x_sec(x_sec_id, lvl_z)
        expression = f'x_sec_id = {x_sec_id} AND not (Sort_Value >= {min(list_left_sort_values_trim1)} ' \
                     f'AND Sort_Value <= {max(list_right_sort_values_trim1)})'
        delete_features_using_expression(pts_high_slopes, expression)
        print(f'Data trimmed.')
        print(f'left sort values = {list_left_sort_values_trim1}')
        print(f'left point_z = {list_left_point_z_trim1}')
        print(f'right sort values = {list_right_sort_values_trim1}')
        print(f'right point_z = {list_right_point_z_trim1}')
    # ---------------------------------------------------------
    print(f'')
    print(f'Step 2: Identify slope gaps and then level again..')
    print(f'------')
    list_left_sv_gap_adj, list_left_point_z_gap_adj, leftGap = slope_gap_adjustment(list_left_sort_values_trim1, list_left_point_z_trim1)
    list_right_sv_gap_adj, list_right_point_z_gap_adj, rightGap = slope_gap_adjustment(list_right_sort_values_trim1, list_right_point_z_trim1)

    if leftGap == 1 or rightGap == 1:  # if there is slope gap affect
        # get extra points and append them to pts_high_slopes
        minExtra = min(list_left_sv_gap_adj) - 1
        maxExtra = max(list_right_sv_gap_adj) + 1
        expression = f'x_sec_id = {x_sec_id} AND Sort_Value in ({minExtra}, {maxExtra})'
        extra_pts = pts_high_slopes + "extra"
        delete_temps([extra_pts])
        arcpy.Select_analysis(in_features=x_sec3d_pts, out_feature_class=extra_pts, where_clause=expression)
        arcpy.Append_management(inputs=extra_pts, target=pts_high_slopes, schema_type="NO_TEST")
        delete_temps([extra_pts])

        # update delete flag
        expression = f'x_sec_id = {x_sec_id} AND not (Sort_Value >= {minExtra} AND Sort_Value <= {maxExtra})'
        flag_to_delete_features_using_expression(pts_high_slopes, expression, 1)

        # get new lists
        expression = f'x_sec_id = {x_sec_id} AND (Sort_Value >= {minExtra} AND Sort_Value <= {max(list_left_sv_gap_adj)})'
        list_left_sv_gap_adj, list_left_point_z_gap_adj = get_lists_for_sv_and_z_for_xsec_id(x_sec_id, expression, "left")
        expression = f'x_sec_id = {x_sec_id} AND (Sort_Value >= {min(list_right_sv_gap_adj)} AND Sort_Value <= {maxExtra})'
        list_right_sv_gap_adj, list_right_point_z_gap_adj = get_lists_for_sv_and_z_for_xsec_id(x_sec_id, expression, "right")

        lvl_z = lvl_elev(list_left_point_z_gap_adj, list_right_point_z_gap_adj)
        print(f'lvl_z after gap treatment = {lvl_z}')
        calc_lvl_for_a_x_sec(x_sec_id, lvl_z)

        new_list_left_sort_values, new_list_left_point_z = trim_list_using_max_elev(lvl_z, list_left_sv_gap_adj,
                                                                                    list_left_point_z_gap_adj)
        new_list_right_sort_values, new_list_right_point_z = trim_list_using_max_elev(lvl_z, list_right_sv_gap_adj,
                                                                                      list_right_point_z_gap_adj)

        print(f'left sort values after gap adjustment = {list_left_sv_gap_adj}')
        print(f'left point_z after gap adjustment = {list_left_point_z_gap_adj}')
        print(f'right sort values after gap adjustment = {list_right_sv_gap_adj}')
        print(f'right point_z after gap adjustment = {list_right_point_z_gap_adj}')

        expression = f'x_sec_id = {x_sec_id} AND not (Sort_Value >= {min(new_list_left_sort_values)} ' \
                     f'AND Sort_Value <= {max(new_list_right_sort_values)})'
        flag_to_delete_features_using_expression(pts_high_slopes, expression, 1)

        print(f'')
        print(f'Data trimmed after slope gaps found:')
        print(f'final left sort_values = {new_list_left_sort_values}')
        print(f'final left point_z = {new_list_left_point_z}')
        print(f'final right sort_values = {new_list_right_sort_values}')
        print(f'final right point_z = {new_list_right_point_z}')
    else:
        print(f'No slope gaps found.')


def x_sec_level_points_tbl_x_id_new_centre_sort_start_ends():
    arcpy.DeleteField_management(in_table=pts_high_slopes,
                                 drop_field="MIN_Sort_Value;MAX_Sort_Value; MAX_NewCentre")

    tbl_x_id_new_centre_sort_start_ends = tempGDB + "//tbl_x_id_new_centre_sort_start_ends"
    delete_temps([tbl_x_id_new_centre_sort_start_ends])

    arcpy.Statistics_analysis(in_table=pts_high_slopes, out_table=tbl_x_id_new_centre_sort_start_ends,
                              statistics_fields="Sort_Value MIN;Sort_Value MAX;NewCentre MAX", case_field="x_sec_id")
    arcpy.JoinField_management(in_data=pts_high_slopes, in_field="x_sec_id",
                               join_table=tbl_x_id_new_centre_sort_start_ends, join_field="x_sec_id",
                               fields="MIN_Sort_Value;MAX_Sort_Value;MAX_NewCentre")
    add_field_with_a_value(pts_high_slopes, "lvl_z", "DOUBLE", "None")  # for future use
    # add_field_with_a_value(pts_high_slopes, "start_sv", "SHORT", "None")  # for future use
    # add_field_with_a_value(pts_high_slopes, "end_sv", "SHORT", "None")  # for future use
    add_field_with_a_value(pts_high_slopes, "flag_delete", "SHORT", "None")  # for future use

    return tbl_x_id_new_centre_sort_start_ends


def x_sec_level_points_list_x_sec_id_MIN_MAX_Sort_Value_NewCentre(tbl_x_id_new_centre_sort_start_ends):

    values = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_new_centre_sort_start_ends, 'x_sec_id')]
    list_x_sec_id = list(values)

    values = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_new_centre_sort_start_ends, 'MIN_Sort_Value')]
    list_MIN_Sort_Value = list(values)

    values = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_new_centre_sort_start_ends,'MAX_Sort_Value')]
    list_MAX_Sort_Value = list(values)

    values = [row[0] for row in arcpy.da.SearchCursor(tbl_x_id_new_centre_sort_start_ends, 'MAX_NewCentre')]
    list_NewCentre = list(values)

    delete_temps([tbl_x_id_new_centre_sort_start_ends])
    return list_x_sec_id, list_MIN_Sort_Value, list_MAX_Sort_Value, list_NewCentre


def get_lists_for_sv_and_z_for_xsec_id(x_sec_id, expression, side):

    pts_high_slopes_for_a_x_sec = pts_high_slopes + str(x_sec_id)
    delete_temps([pts_high_slopes_for_a_x_sec])
    arcpy.Select_analysis(in_features=pts_high_slopes, out_feature_class=pts_high_slopes_for_a_x_sec,
                          where_clause=expression)
    list_sort_values = []
    list_POINT_Z = []
    if side in ("right", None):
        cursor = arcpy.da.SearchCursor(pts_high_slopes_for_a_x_sec, ['Sort_Value', 'POINT_Z'],
                                       sql_clause=(None, 'ORDER BY Sort_Value'))
    elif side == "left":
        cursor = arcpy.da.SearchCursor(pts_high_slopes_for_a_x_sec, ['Sort_Value', 'POINT_Z'],
                                       sql_clause=(None, 'ORDER BY Sort_Value DESC'))
    for row in cursor:
        list_sort_values.append(row[0])
        list_POINT_Z.append(row[1])

    delete_temps([pts_high_slopes_for_a_x_sec])
    return list_sort_values, list_POINT_Z


# -------------------------------------------------------------------------------------------------------------------
# Bank full width line and poly functions
# --------------------------------------------------------------------------------------------------------------------


def x_sec_bfw_poly(x_sec3d_levelled_lines, output_bfw_poly):
    left_pts = tempGDB + "\\left_pts"
    right_pts = tempGDB + "\\right_pts"
    merge_pts = tempGDB + "\\merge_pts"

    left_pts_line = tempGDB + "\\left_pts_line"
    right_pts_line = tempGDB + "\\right_pts_line"
    merge_pts_line = tempGDB + "\\merge_pts_line"

    bfw_poly_v1 = tempGDB + "\\bfw_poly_v1"

    delete_temps([left_pts, right_pts, merge_pts, left_pts_line, right_pts_line, merge_pts_line, bfw_poly_v1])

    arcpy.FeatureVerticesToPoints_management(in_features=x_sec3d_levelled_lines,
                                             out_feature_class=left_pts, point_location="START")
    arcpy.FeatureVerticesToPoints_management(in_features=x_sec3d_levelled_lines,
                                             out_feature_class=right_pts, point_location="END")
    arcpy.Merge_management(inputs=f'{right_pts};{left_pts}', output=merge_pts)

    arcpy.PointsToLine_management(Input_Features=left_pts, Output_Feature_Class=left_pts_line,
                                  Line_Field="seg_id", Sort_Field="x_sec_id", Close_Line="NO_CLOSE")
    arcpy.PointsToLine_management(Input_Features=right_pts, Output_Feature_Class=right_pts_line,
                                  Line_Field="seg_id", Sort_Field="x_sec_id", Close_Line="NO_CLOSE")
    arcpy.PointsToLine_management(Input_Features=merge_pts,
                                  Output_Feature_Class=merge_pts_line, Line_Field="seg_id",
                                  Sort_Field="x_sec_id", Close_Line="NO_CLOSE")

    arcpy.FeatureToPolygon_management(in_features=f'{merge_pts_line};{right_pts_line};{left_pts_line}',
                                      out_feature_class=bfw_poly_v1, cluster_tolerance="",
                                      attributes="NO_ATTRIBUTES", label_features="")
    arcpy.Dissolve_management(in_features=bfw_poly_v1, out_feature_class=output_bfw_poly,
                              dissolve_field="", statistics_fields="", multi_part="SINGLE_PART",
                              unsplit_lines="DISSOLVE_LINES")

    delete_temps([left_pts, right_pts, merge_pts, left_pts_line, right_pts_line, merge_pts_line, bfw_poly_v1])


# -------------------------------------------------------------------------------------------------------------------
# General functions
# --------------------------------------------------------------------------------------------------------------------


def add_field_with_a_value(fc, fld_name, fld_type, fld_value):
    if not has_fld(fc, fld_name):
        # add field and calculate field value "
        arcpy.AddField_management(fc, fld_name, fld_type)
        arcpy.CalculateField_management(fc, fld_name, fld_value, "PYTHON")
    else:
        # field exists, just calculate value
        arcpy.CalculateField_management(fc, fld_name, fld_value, "PYTHON")


def create_temp_environ(drive):
    out_folder = "temp_w"
    out_folder_path = drive + "\\" + out_folder

    fgdb = "temp_fGDB.gdb"

    temp_w = out_folder_path + "\\" + fgdb
    temp_env = [out_folder_path, temp_w]

    if not arcpy.Exists(out_folder_path):
        # print("Does not exist")
        arcpy.CreateFolder_management(drive, out_folder)
        arcpy.CreateFileGDB_management(out_folder_path, fgdb)
    else:
        # print("Does exist")
        arcpy.Delete_management(temp_w)
        arcpy.CreateFileGDB_management(out_folder_path, fgdb)

    return temp_env


def delete_features_using_expression(pts_high_slopes, expression):
    # print(expression)
    arcpy.MakeFeatureLayer_management(in_features=pts_high_slopes,
                                      out_layer="pts_high_slopes_lyr")
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_lyr",
                                            selection_type="NEW_SELECTION", where_clause=expression)
    arcpy.DeleteFeatures_management(in_features="pts_high_slopes_lyr")
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_lyr",
                                            selection_type="CLEAR_SELECTION", where_clause="")
    delete_temps(["pts_high_slopes_lyr"])


def delete_temps(temp_list):
    for item in temp_list:
        if arcpy.Exists(item):
            arcpy.Delete_management(item)
            # print(f'Deleted temp file {item}.')


def flag_to_delete_features_using_expression(pts_high_slopes, expression, value):
    # print(expression)
    arcpy.MakeFeatureLayer_management(in_features=pts_high_slopes,
                                      out_layer="pts_high_slopes_lyr")
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_lyr",
                                            selection_type="NEW_SELECTION", where_clause=expression)
    arcpy.CalculateField_management(in_table="pts_high_slopes_lyr", field="flag_delete",
                                    expression=int(value), expression_type="PYTHON",
                                    code_block="")
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_lyr",
                                            selection_type="CLEAR_SELECTION", where_clause="")
    delete_temps(["pts_high_slopes_lyr"])


def has_fld(fc, field_name):
    lst_fields = arcpy.ListFields(fc)
    x = False
    for field in lst_fields:
        if field.name == field_name:
            x = True
            return x


def trim_list_using_max_elev(lvl_z, list_sort_values, list_point_z):
    """
    This will send the new limits based lvl_z
    :param lvl_z:
    :param list_sort_values:
    :param list_point_z:
    :return:
    """
    list_sort_values_lvl = []
    list_point_z_lvl = []

    if len(list_sort_values) < 3:
        list_sort_values_lvl = list_sort_values
        list_point_z_lvl = list_point_z
    else:
        i = 0
        for item in list_sort_values:
            sv = list_sort_values[i]
            z = list_point_z[i]
            if z <= lvl_z:
                list_sort_values_lvl.append(sv)
                list_point_z_lvl.append(z)
            i += 1
    # ----------------------
    return list_sort_values_lvl, list_point_z_lvl


def x_sec_calc_lvl_z_for_xsection(pts_high_slopes_left_or_right, x_sec_id, lvl_z):
    delete_temps(["pts_high_slopes_left_or_right_lyr"])
    arcpy.MakeFeatureLayer_management(in_features=pts_high_slopes_left_or_right,
                                      out_layer="pts_high_slopes_left_or_right_lyr")
    expression = f'x_sec_id = {x_sec_id}'
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_left_or_right_lyr",
                                            selection_type="NEW_SELECTION", where_clause=expression)

    arcpy.CalculateField_management("pts_high_slopes_left_or_right_lyr", "lvl_z", lvl_z)
    arcpy.SelectLayerByAttribute_management(in_layer_or_view="pts_high_slopes_left_or_right_lyr",
                                            selection_type="CLEAR_SELECTION")
    delete_temps(["pts_high_slopes_left_or_right_lyr"])


# --------------------------------------------------------------------------------------------------------------------

root = Tk()
root.title("Bankfull x-sections")
root.resizable(width=False, height=False)

# Canvas
canvas = Canvas(root, width=700, height=500)
canvas.grid(columnspan=2, rowspan=12)

# Logo
logo = Image.open('werg_logo.jpg')
# logo = Image.open('../werg_logo.jpg')
logo = ImageTk.PhotoImage(logo)
logo_label = Label(image=logo)
logo_label.image = logo

# Title
lbl_title = Label(root, text="Cross Sections & Dimensions 1.0", font=("Raleway", 12, 'bold'))

# Status
default_status = "(Kunapo and Russell, 2021)"
lbl_status = Label(root, text=default_status, font=("Raleway", 10, 'bold'), bd=1, relief=SUNKEN, width=80)

# Input - stream layer
lbl_mwstr = Label(root, text="Input stream :", font="Raleway")
entry_mwstr_path = Entry(root, text="", font="Raleway", width=50)
entry_mwstr_path.insert(0, default_in_mwstr)

# Input - DEM path
lbl_dem = Label(root, text="Input DEM :", font="Raleway")
entry_dem = Entry(root, text="", font="Raleway", width=50)
entry_dem.insert(0, default_in_dem)

# Input - Output Location
lbl_gdb = Label(root, text="Output Location :", font="Raleway")
entry_out_loc = Entry(root, text="", font="Raleway", width=50)
entry_out_loc.insert(0, default_out_location)

# Frame 1 --------------------------------------------------------------------------------------------------------
frame1 = Frame(root, borderwidth=5, relief='raised')
# Station points
chk_btn_stnpts_var = IntVar()
# chk_btn_stnpts_var.set(1)
chk_btn_stnpts = Checkbutton(frame1, text="Station points interval (m) : ", font="Raleway",
                             variable=chk_btn_stnpts_var)
entry_interval = Entry(frame1, text="", font="Raleway", width=3)
entry_interval.insert(0, "25")

# 2D x-section
chk_btn_2D_x_secs_var = IntVar()
chk_btn_2D_x_secs = Checkbutton(frame1, text="2D x-section half width (m) :", font="Raleway",
                                variable=chk_btn_2D_x_secs_var)
width_options = [20, 30, 40, 50, 60, 70, 80, 90, 100]
width_selected = IntVar()
width_selected.set(width_options[1])
width_menu = OptionMenu(frame1, width_selected, *width_options)
width_menu.config(font="Raleway", width=3)

# 3D x-section
chk_btn_3D_x_secs_var = IntVar()
chk_btn_3D_x_secs = Checkbutton(frame1, text="3D x-sections with elevation and slope", font="Raleway",
                                variable=chk_btn_3D_x_secs_var)
# Levelled
chk_btn_3D_x_secs_slope_lvl_var = IntVar()
chk_btn_3D_x_secs_slope_lvl = Checkbutton(frame1, text="Levelled bank full width at slope (deg) >",
                                          font="Raleway", variable=chk_btn_3D_x_secs_slope_lvl_var)
entry_slope = Entry(frame1, text="", font="Raleway", width=3)
entry_slope.insert(0, "7")

# Apply upstream correction
chk_btn_upstream_level_correction_var = IntVar()
chk_btn_upstream_level_correction = Checkbutton(frame1, text="Apply Longitudinal Correction",
                                          font="Raleway", variable=chk_btn_upstream_level_correction_var)

# Process button
# global btn_process
btn_process = Button(root, text="Process", font=("Raleway", 12, 'bold'), bg="#003d68", fg='white', height=2, width=20,
                     command=main_process)

# ---------------------------------------------------------------------------------------------------------------------
# Positioning onto the screen
logo_label.grid(columnspan=2, row=0, column=0, pady=5)

lbl_title.grid(columnspan=2, row=1, column=0, pady=10)

lbl_mwstr.grid(row=2, column=0, sticky='e', pady=5)
entry_mwstr_path.grid(row=2, column=1, sticky='w', pady=5)

lbl_dem.grid(row=3, column=0,  sticky='e', pady=5)
entry_dem.grid(row=3, column=1,  sticky='w', pady=5)

lbl_gdb.grid(row=4, column=0, sticky='e', pady=5)
entry_out_loc.grid(row=4, column=1, sticky='w', pady=10)

frame1.grid(columnspan=2, row=7, pady=10)
chk_btn_stnpts.grid(row=5, column=0, sticky='w')
entry_interval.grid(row=5, column=1, sticky='w')

chk_btn_2D_x_secs.grid(row=6, column=0, sticky='w')
width_menu.grid(row=6, column=1, sticky='w')

chk_btn_3D_x_secs.grid(row=7, column=0, sticky='w')

chk_btn_3D_x_secs_slope_lvl.grid(row=8, column=0, sticky='w')
entry_slope.grid(row=8, column=1, sticky='w')

chk_btn_upstream_level_correction.grid(row=10, column=0, sticky='e')

btn_process.grid(columnspan=2, row=10, pady=20)

lbl_status.grid(columnspan=2, row=11, pady=5)
# --------------------------------------------------------------------------------------------------------------------

root.mainloop()

