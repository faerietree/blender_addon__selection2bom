#-------------------------------------------------------------------------------
#!/usr/bin/env python
# ========= BLENDER ADD-ON =====================================================
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name":         "Selection 2 Bill of Materials",
    "author":       "macouno, Yorik van Havre, Jan R.I.B.-Wein",
    "version":      (2, 0),
    "blender":      (2, 7, 3),
    "location":     "View3D > Tool Shelf > Misc > Selection to Bill of Materials",
    "description":  "Either creates a Bill of Materials out of selected objects"
            " (including group instances). Or selects all objects of the current"
            " scene that are not hidden automatically while sorting out rendering-"
            " or animation-related objects like lighting, cameras and armatures."
            "\r\n'Material:<Material>' in the object name overrides material(s)."
            "\r\nBy default group instances are resolved to the objects of the group"
            " i.e. a group or instance thereof is no individual standalone part."
            "\r\nAn option to consider group instances as complete independent"
            " standalone parts exists. The objects are not resolved and a BoM entry"
            " for each group instance is created!"
            "\r\nIn the hybrid mode the group instances and count are listed as part."
            " In addition every assembly and the objects it is made from are listed."
            " Nevertheless each of these 'assemblies' is resolved if the same group +"
            " delta transform combination of the instance empty has not occurred before"
            " influencing the resulting dimensions."
            "\r\nObject label, material, dimensions distinguish parts."
            "\r\nUsage: Hide objects that shall be excluded from the BoM or select"
            " objects to be included in the BoM explicitely. If no selection is given"
            " then all the not hidden objects and group instances are examined."
            "\r\nThe dimensions are calculated from group instance inherited total scale"
            " times the object dimensions. => Model measurements need to be in real"
            " world size/units or at least have to be scaled to the desired units!",
    "wiki_url":     "http://github.com/faerietree/selection2bom",
    "tracker_url":  "https://projects.blender.org/tracker/index.php?"
                    "func=detail&aid=",
    "category":     "Object"
    #,"warning":      ""
}


# ------- DESCRIPTION ----------------------------------------------------------
#
# """PURPOSE"""
# CREATING A BILL OF MATERIALS OUT OF SELECTED OBJECTS.
#
#
# """WHAT IT DOES"""
# Depending on settings: (default setting is to resolve selected groups)
#
# - either iterate selected objects only and create a bom entry
#   where the dimensions are calculated from the scale.
#
# - or the above and additionally resolve groups and sort out rendering-related
#   objects like lighting, cameras and armatures (animation related objects).

# ------- LICENSING ------------------------------------------------------------
# Created by FarieTree Productions (i@ciry.at)
# It's free, as is, open source and property to the World. But without warranty.
# Thus use it, improve it, recreate it and please at least keep the
# origin as in usual citation, i.e. include this Copyright note.
# LICENSE: creative commons, non-commercial, share-alike.
#
# ------------------------------------------------------------------------------



#------- IMPORTS --------------------------------------------------------------#
import bpy
import re
import os
import math
import time

from bpy.props import IntProperty, StringProperty, BoolProperty, EnumProperty




#------- GLOBALS --------------------------------------------------------------#
# Show debug messages in blender console (that is the not python console!)
debug = True




#------- FUNCTIONS ------------------------------------------------------------#
#
# Guarantuee a valid initial state.
#
def initaddon(context):
    global bom_entry_count_map
    global bom_entry_info_map
    global bom_entry_variant_map
    global assembly_count_map
    global assembly_bom_entry_count_map
    bom_entry_count_map = {}
    bom_entry_info_map = {}  # url, part id, ...
    bom_entry_variant_map = {}  # apply modifiers, then different volume => different postprocessing/part/variant ...
    assembly_count_map = {}
    assembly_bom_entry_count_map = {}
    
    global entry_count_highest_digit_count
    entry_count_highest_digit_count = 0
    global object_longest_label_len
    object_longest_label_len = 0
    global material_longest_label_len
    material_longest_label_len = 0

    global cache_resolved_dupli_group_dimensions_map
    cache_resolved_dupli_group_dimensions_map = {}
    
    global cache_resolved_dupli_group_volume_map
    cache_resolved_dupli_group_volume_map = {}


#
# Select visible, compatible objects automatically.
#
def select_automagically(context):
    #if debug:
    print('No selection! Automatically guessing what to select. (hidden objects are not selected)')
    # Ensure nothing is selected
    if debug:
        print('deselecting all.')
    deselect_all(context)
    # Select depending on if it is a mechanical object. TODO Improve decision taking.
    for o in context.scene.objects:
        if debug: 
            print('Scene object: ', o)
        if (o.hide):# Here we skip hidden objects no matter settings as this way
                # one has the choice to either include object via selecting or
                # or exlude objects by hiding those.
            if debug:
                print('Auto-selection: Hidden scene object ', o, '.')
            continue
        if (o.type != None):
            if debug:
                print('Type of scene object: ', o, ' = ', o.type)
            # dupli group can theoretically be attached to any object, but we only consider those:
            if (not is_object_type_considered(o.type)):
                continue
            is_longest_object_label_then_store_len(o)  # keep track of longest label length
            is_longest_material_then_store_len(material=o.active_material)
            o.select = True  # select object
            context.scene.objects.active = o  # make active
            if debug:
                print('Selected object: ', o, ' \tactive object: ', context.scene.objects.active)
                
    # Select object instances depending on if it is a mechanical object. TODO Improve criteria.
    for ob in context.scene.object_bases:
        if debug: 
            print('Scene object base: ', ob)
        o = ob.object
        if (o.hide):# Here we skip hidden objects no matter settings as this way
                # one has the choice to either include object via selecting or
                # or exlude objects by hiding those.
            if debug:
                print('Auto-selection: Hidden underlaying object ', o, ' of object base ', ob, '.')
            continue
        if (o.type != None):
            if debug:
                print('Type of scene object: ', o, ' = ', o.type)
            if (not is_object_type_considered(o.type)):
                continue
            # Increase the counter for this object as another reference was found?
            if (not (o in object_reference_count)):# || object_reference_count[o] is None):
                object_reference_count[o] = 0
            object_reference_count[o] = object_reference_count[o] + 1
            # Keep track of the longest label's length
            is_longest_object_label_then_store_len(o)
            is_longest_material_then_store_len(material=o.active_material)
            # Select the object reference. TODO Select the object or the reference?
            ob.select = True  #select object
            context.scene.objects.active = o    #make active
            if debug:
                print('Selected object: ', ob, ' \tactive object: ', context.scene.objects.active)
                  

#
# ACT
# @return always returns True or False
object_reference_count = {}
def act(context):
    global bom_entry_count_map
    global bom_entry_info_map
    global assembly_count_map
    global assembly_bom_entry_count_map
    
    initaddon(context)

    if debug:
        print('Engine started ... (acting according to setting)')
    ############
    #preparation - selection
    ############
    scene_layers_to_restore = list(context.scene.layers) # get a copy.
    #if debug:
    #    print('Should be true: ', id(scene_layers_to_restore), ' != ', id(context.scene.layers))
    
    #----------#
    # At this point a selection must have been made either using
    # 'select by pattern' add-on or by manually selecting the objects/items.
    #----------#
    # Otherwise an effort is undertaken to automatically select mechanical parts.(visible only)
    if (context.selected_objects is None or len(context.selected_objects) == 0):
        select_automagically(context)
    else:
       # Ensure that all layers are visible to prevent resolved objects (from group instances) not
       # being listed in the BoM.
       context.scene.layers = (True, True, True, True, True,  True, True, True, True, True,  True,
               True, True, True, True, True,  True, True, True, True)

    ############
    # Now there must be a selection or we abort the mission.
    ############
    #Now at last we have a selection? Either set up manually or selected automatically.
    if (len(context.selected_objects) == 0):
        if debug:
            print('Selection is still empty! Mission aborted.')
        return {'CANCELLED'}
        
    ############    
    # Filelink attribute to be determined according to scene label
    # or active object or selection object at position 0:
    ############
    filelink = build_filelink(context)
    
    
    ##########
    # OBJECTS (including group instances as those are attached to objects, see dupligroup 
    #          http://wiki.blender.org/index.php/Doc:2.7/Manual/Modeling/Objects/Duplication/DupliGroup)
    ##########
    result = create_bom_entry_recursively(context, context.selected_objects.copy(), [], filelink=filelink)#no deepcopy as the objects
                                                           #in the dictionary shall keep their live character!
                                                           #This was required because we have to create new
                                                           #temporary selections later on while diving deep
                                                           #in the create_bom_entry_recursion adventure!
    #Something went wrong?
    if (result is None or not result):
        if debug:
            print('creating bom entry not successful => aborting')
        #return False#selection_result
    else:
        write2file(context, bom_entry_count_map, bom_entry_info_map, assembly_count_map, assembly_bom_entry_count_map, filelink)

    context.scene.layers = scene_layers_to_restore


    return {'FINISHED'} # Because groups itself not yet are supported and are a distinct mode in itself.



    ##########
    # GROUPS (not group instances, those are attached to objects and therefore already handled above when iterating the scene objects!)
    ##########
    #Groups are not represented by any data in a scene. As such it's no problem if the objects in a scene are wildly grouped.
    #Those groups will have no influence on the generated Bill of Materials (BoM). Only instances have an effect.
    #The effect of group instances is twofold:
    #1) Instances are high level parts, containing objects, i.e. other parts.
    #2) Instances are self-contained standalone parts.
    
    #(And should not be resolved. => Here the material has to be specified explicitely or will be stated as mixed.)
    
    #global bom_entry_count_map
    #bom_entry_count_map = {}    #clear the map/dictionary --> now appending to the already created BoM for objects/group instances.
    append_to_file(context, "\r\n\n\nGROUPS OF SCENE\r\n")
    #TODO Create separate bom_entry_count_map for groups, because until now here several lines are added redundantly!
    
    
    for g in bpy.data.groups:#bpy.types.BlendData.groups:

        #examine if all objects are in the current context scene
        are_all_objects_in_context_scene = True
        for o in g.objects:
            if not o.is_visible(context.scene):
                are_all_objects_in_context_scene = False
                break#cancel further examination
        
        #Is this group not completely in the current/context scene?
        if (not are_all_objects_in_context_scene):
            if debug:
                print('Not all objects of this group ', g, ' are (visible) in this scene: ', context.scene)
            continue#next Group within the blend file
            
        #Add this group to the bill of materials as standalone complete part on its own (not resolving to objects)?
        if (not context.scene.selection2bom_in_mode == '0'):#not resolve_groups):
            #group has a partname identifier and this hopefully contains a material:<material>,
            # => try to compile a bom entry out of this, if not possible then lookup the material from the objects,
            # => i.e. either compose a list of materials being used in the group (Aluminium, Stainless Steel, Diamond)
            #         or give a label like 'mixed'.
            # If no material can be resolved then use 'undefined' or rather '-'.
            bom_entry = build_and_store_bom_entry_out_of_group(context, g)
            append_to_file(context, bom_entry)
            #resolve all group instances created out of this group:
            for o_g in g.users_dupli_group:
                #examine group instance
                if o_g.dupli_group is None or len(o_g.dupli_group.objects) == 0:
                    if debug:
                        print('dupli group/group instance was None/null or no objects'
                                'were contained. Object count: ', len(o_g.dupli_group.objects))
                    continue
                
                bom_entry = build_and_store_bom_entry(context, o_g, filelink=filelink)
                #build_bom_entry() is not enough as we have to keep track of the occurence counts => and store
                append_bom_entry_to_file(context, bom_entry)
        
            
            continue#no further examination of the group's objects
        
        #######
        # RESOLVE GROUP TO OBJECTS
        #######
        #Then in this mode all the objects that make up the group are put into the bill of materials separately.
        for o in g.objects:
            bom_entry = build_and_store_bom_entry(context, o, filelink=filelink)
            #build_bom_entry() is not enough as we have to keep track of the occurence counts => and store
            append_bom_entry_to_file(context, bom_entry)
            

        

        
    #Everything was fine then!
    return True#selection_result
    
    ############
    #act-furthermore
    ############
    #nothing so far ..
    #but a smiley :) highly underestimated



#
#
#
object_longest_label_len = 0
def is_longest_object_label_then_store_len(o):
    global object_longest_label_len
    #keep track of the longest object name to fill up with zeros not to break the bill of materials structure:
    o_label = getBaseName(o.name)
    letter_count = len(o_label)
    if (letter_count > object_longest_label_len):
        object_longest_label_len = letter_count
        if debug:
            print("Keeping track of longest object label's length. New longest length: ", object_longest_label_len)
    #elif debug:
    #    print("Keeping track of longest object label's length. Longest length (no change): ", object_longest_label_len)



#
#
#
material_longest_label_len = 0
#def is_longest_material_then_store_len(material):
def is_longest_material_then_store_len(material_label='', material=None):
    global material_longest_label_len
    if (material is None and material_label == ''):
        return False
    #keep track of the longest material name to fill up with zeros not to break the bill of materials structure:
    m_label = '-'
    if (material is None):
        m_label = getBaseName(material_label)
    else :
        m_label = getBaseName(material.name)
        
    letter_count = len(m_label)
    if (letter_count > material_longest_label_len):
        material_longest_label_len = letter_count
        if debug:
            print('Keeping track of longest material label\'s length. Longest length: ', material_longest_label_len)
    #elif debug:
    #    print('Keeping track of longest material label\'s length. Longest length (no change): ', material_longest_label_len)



#
#
#
entry_count_highest_digit_count = 0
def is_longest_entry_count_then_store_len(entry_count):
    global entry_count_highest_digit_count
    count = len(str(entry_count))
    if (count > entry_count_highest_digit_count):
        entry_count_highest_digit_count = count
        if debug:
            print("Keeping track of longest entry count, i.e. highest digit count: ", entry_count_highest_digit_count)
    #elif debug:
    #    print("Keeping track of longest entry count, i.e. highest digit count (no change): ", entry_count_highest_digit_count)










#CREATE BOM ENTRY FROM OBJECT
def create_bom_entry_recursively(context, o_bjects, owning_group_instance_objects, recursion_depth=0, filelink=None):
    if debug:
        print(str(recursion_depth) + ' Creating BoM entry recursively ...')
        
    if (recursion_depth > context.scene.after_how_many_create_bom_entry_recursions_to_abort):
        if debug:
            print('Failed creating bom entries in time. Recursion limit exceeded: '
                    , recursion_depth)
        return {'CANCELLED'}


    
    if debug:
        print(str(recursion_depth) + ' Encountered: ', o_bjects, ' type: ', type(o_bjects))
    
    
    
    #termination condition will be checked here:
    #-------
    # OBJECT?
    #-------
    if type(o_bjects) is bpy.types.Object:
        
        is_longest_object_label_then_store_len(o_bjects)
        if debug:
            print(str(recursion_depth) + ' Encountered an object: ', o_bjects, ' blender-Type: ', o_bjects.type)
        
        
        #Is object type considered? (not considered are e.g. armatures.)
        #dupligroup/groupinstance can theoretically be attached to any object, but we only consider those:
        if (is_object_type_considered(o_bjects.type)):#(o_bjects has to be an object for type to exist)

            #is_to_be_listed_into_bom = False
            # Evaluate the object type and current mode:

            #Is not a group instance?        
            if (o_bjects.dupli_group is None):
                    #or o_bjects.dupli_type is not 'GROUP'<--TODO:superfluous? What effects does changing the duplitype setting have?
                if (not o_bjects.is_visible(context.scene)):
                    if debug:
                        print('Object ', o_bjects,' is not visible in the current scene: ', context.scene)
                    return {'CANCELLED'}
                    
                # This object is not functioning as a group instance container!
                # In all modes, these objects get an entry in the BoM.
                if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_objects, filelink=filelink)):
                    if debug:
                        print('Failed to write bom entry to file. ', o_bjects, recursion_depth)
                    return {'CANCELLED'}
                    
                return {'FINISHED'}


            #NOTE: PAY ATTENTION TO BLANK LINES - COMPILER COULD ASSUME THE ELIF STATEMENT IS ALREADY DONE.
            
            #Is a group instance?
            elif (o_bjects.dupli_group is not None
                    #and o_bjects.dupli_type is 'GROUP'<--TODO:superfluous? What effects does changing the duplitype setting have?
                    #THE DUPLI_TYPE IS ONLY RELEVANT FOR NEWLY CREATED DUPLICATIONS/REFERENCES FROM THE OBJECT!
                    #THE TYPE OF THE GROUP (o_bjects.dupli_group:bpy.types.Group) IS INTERESTING BUT IS 'GROUP' ANYWAY ELSE IT WERE NO GROUP!
                    #Is a group but has no objects in the group?
                    and (len(o_bjects.dupli_group.objects) > 0)): # If no objects are linked here the creation of a BoM entry is pointless.
                if debug:
                    print('It\'s a Group instance! Attached dupli group: ', o_bjects.dupli_group)
                    
                #Resolving groups is not desired?
                if (context.scene.selection2bom_in_mode == '0'):
                    if debug:
                        print('Group shall not be resolved. Is considered a standalone complete part on its own.')
                    #This object is functioning as a group instance container and resembles a standalone mechanical part!
                    #is_to_be_listed_in_bom = True
                    if (not o_bjects.is_visible(context.scene)):
                        if debug:
                            print('Object ', o_bjects,' is not visible in the current scene: ', context.scene)
                        return {'CANCELLED'}
                    if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_objects, filelink=filelink)): #<-- still attach it to a possible parent group instance.
                        if debug:
                            print('Failed to write bom entry of group instance to file: ', o_bjects, '\t dupli group: ', o_bjects.dupli_group)
                        return {'CANCELLED'}
                    return {'FINISHED'}
                    
                # Hybrid mode? i.e. list in bom and resolve objects too?
                elif (context.scene.selection2bom_in_mode == '2'):
                    if debug:
                        print('Hybrid Mode: Group instances/assemblies are both listed in the bom and resolved.')#,
                        #' A tree is the desired result, i.e. This assembly exists x times and it is assembled',
                        #' using the following parts.')
                    #is_to_be_listed_in_bom = True
                    #is_group_instance_and_needs_to_be_resolved = True
                    if (not o_bjects.is_visible(context.scene)):
                        if debug:
                            print('Object ', o_bjects,' is not visible in the current scene: ', context.scene)
                        return {'CANCELLED'}
                    if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_objects, filelink=filelink)):
                        if debug:
                            print('Failed to write bom entry of group instance to file: ', o_bjects, '\t dupli group: ', o_bjects.dupli_group)
                # Both mode 1 and 2 need to resolve the group into its objects (if they are not atomar):
                if (is_object_atomar(o_bjects)):
                    return {'FINISHED'}

                # Attempt to resolve the group instance into the objects the group contains:
                resolve_group_result = o_bjects.dupli_group.objects#resolve_group(group)
                
                #if (context.scene.selection2bom_in_mode == '2'):
                #    build_and_store_bom_entry(context, '------- Parts of assembly `' + o_bjects.dupli_group.name + '`: -------')
                #    #more generic as not every group instance may be a coherent assembly: build_and_store_bom_entry(context, '------- Grouped Parts `' + o_bjects.dupli_group.name + '`: -------')
                if (resolve_group_result is None or (len(resolve_group_result) < 1)):
                    #Group was not resolved successfully!
                    if debug:
                        print('Failed to resolve a group or group was empty. ', str(o_bjects.dupli_group))
                    return {'CANCELLED'}
                    
                # Group resolved into objects!
                if debug:
                    print('Resolved a group. Count of objects in group: ', len(resolve_group_result))
                owning_group_instance_objects.append(o_bjects) 
                for obj in resolve_group_result:
                    print(obj, " ==? ", o_bjects)
                    if obj == o_bjects:# or obj.name == o_bjects.name:
                        print("Skipping resolved object because it is the given object itself: ", obj)
                        continue
                    create_bom_entry_recursively(context, obj, owning_group_instance_objects, recursion_depth=(recursion_depth + 1), filelink=filelink)
                
                owning_group_instance_objects.remove(o_bjects)

                #if (context.scene.selection2bom_in_mode == '2'):
                #    build_and_store_bom_entry(context, '------- Parts of assembly `' + o_bjects.dupli_group.name + '` -END -------')
                return {'FINISHED'}
                 
            else:
                #if no objects are linked here the creation of a BoM entry is pointless
                if debug:
                    print('It may be a group instance ', o_bjects.dupli_group, ' but has no objects: ', o_bjects.dupli_group.objects)
                return {'CANCELLED'}
           
            
            
        #Object type is not considered then:
        else:
            if (debug):
                print(str(recursion_depth) + ' Object type ', o_bjects.type, ' is not considered (e.g. armatures are not considered a mechanical part).')
            return {'CANCELLED'}
            
        
        
    #-------
    # LIST?
    #-------
    elif (o_bjects is list or type(o_bjects) is list):
        if debug:
            print('>> Object is list: ' + str(o_bjects) + ' | type:' + str(type(o_bjects)))
        for o in o_bjects:
            create_bom_entry_recursively(context, o, owning_group_instance_objects, recursion_depth=(recursion_depth + 1), filelink=filelink)
        return {'FINISHED'}




    #this time none of the above conditions was met:
    if debug:
        print('Did not match any branch for creating a BoM entry:', o_bjects, ' type:', type(o_bjects))
    
    return {'FINISHED'}



#
# If a object type is considered or rather if an object type is ignored, i.e. filtered out.
# This is useful for skipping animation related objects which shall e.g. not occur in a BOM.
#
def is_object_type_considered(object_type):
    #dupligroup/groupinstance can theoretically be attached to any object, but we only consider those:
    return object_type == 'MESH' or object_type == 'EMPTY' or object_type == 'CURVE'
            #TODO type is not related to being mechanical part or not!
            #or not skip_non_mechanical_objects;#<- overwrites the above and renders all types valid
    #EMPTY for group instances (even though instances can be attached to any other than empty object too!)

PATTERN_OPTIONAL = '(optional' + '[-_ ]+|[-_ ]+optional)'
PATTERN_ATOM = '(atom' + '[-_ ]+|[-_ ]+atom)'
def is_object_atomar(o):
    return (re.search(PATTERN_ATOM, o.name.lower()) != None)
    
def is_object_optional(o):
    return (re.search(PATTERN_OPTIONAL, o.name.lower()) != None)
    


#
# Builds a BOM ENTRY from an object.
# If a dupligroup/instance is attached to the object, this group is:
#   1) either resolved to its original group and the objects within this group are put into the BoM,
#   2) or the group instance's name is parsed for a assigned material (as a group does not have a material assigned directly)
#      or the material is resolved from contained objects or a the material 'mixed' or 'undefined' is assigned.
# It is being examined how often objects occur to calculate the part count.
# ATTENTION: better don't use user_count blender python API variable because it's not sure that all those user references
# were within the current scene or file or if it was selected anyways!


#def write_bom_entry_to_file(context, o):
#    bom_entry = build_bom_entry(context, o, filelink=filelink)
#    return write2file(context, bom_entry)
    #ATTENTION: BETTER FIRST CREATE ALL BOM ENTRIES, STORING THEM IN THE UNIQUE ENTRY LIST,
    #INCREMENTING THE EQUAL BOM ENTRY COUNT AND ONLY THEN WRITE THIS TO FILE!
  
  
  
bom_entry_count_map = {}
bom_entry_info_map = {}  # url, part id, ...
assembly_count_map = {}
assembly_bom_entry_count_map = {}
#def init_bom_entry_count_map():
#   pass
def build_and_store_bom_entry(context, o, owning_group_instance_objects, filelink=None):#http://docs.python.org/2/tutorial/datastructures.html#dictionaries =>iteritems()
    global bom_entry_count_map
    global bom_entry_info_map
    global bom_entry_variant_map
    global assembly_count_map
    global assembly_bom_entry_count_map
    
    # Also give parent group instance/assembly to allow to inherit its delta transforms:
    bom_entry = build_bom_entry(context, o, owning_group_instance_objects, filelink=filelink, delete_join_result_if_differs=False)#http://docs.python.org/3/tutorial/datastructures.html#dictionaries => items()
    resulting_o = context.scene.objects.active # for volume calculation.
    
    #if debug:
    print('Generated BoM entry: ', bom_entry)
    
    # Store info like URL, part number, ...
    if o.data:
        bom_entry_info = getBaseName(o.data.name)  # Object data (e.g. mesh) makes sense as base parts, as modifiers operate on objects. i.e. if the mesh is equal, then the part to be ordered also probably is equal. e.g. Many things can be manufactured out of a metal block.
        # Though if the size is different this requires to duplicate and change the data (scale the mesh). A workaround for this is to multiply by the object scale but that's not helping if the link is pointing to a too small/big part as the URI generally can't be corrected automatically.
        # Upside is that the amount of data to maintain is less. Though as objects can be interlinked too, that may be true for objects too. Though often rotation and location is wanted separate which would lead to lots of redundant URLs, ... to adapt.
        # Despite that issue, this approach is taken. The persuading argument is that often the link points to a page where the part can be bought from. These pages often let select a size, which obsoletes the issue as the link to several part sizes is the same. For part numbers this is not true. Though part numbers are discouraged as they are an artificial map between parts, introducing a new layer of things to lookup which is not helpful. A part is already completely identified by the function it fulfills and its dimension.
        if not bom_entry in bom_entry_info_map:
            bom_entry_info_map[bom_entry] = bom_entry_info
        else:
            if bom_entry_info_map[bom_entry] != bom_entry_info:
                if debug:
                   print('build_and_store_bom_entry(): Info already determined but the new information differs. current: ', bom_entry_info_map[bom_entry], ' vs. new: ', bom_entry_info)
            
    
    # NOTE This may be moved to build_bom_entry once it is included in the bom entry itself. Currently volume is treated separately.
    volume = -1
    global cache_resolved_dupli_group_volume_map
    if o.dupli_group and o.dupli_group in cache_resolved_dupli_group_volume_map:
        volume = cache_resolved_dupli_group_volume_map[o.dupli_group]
        print("Using cached volume: ", volume)
    elif resulting_o.type != 'EMPTY':
        # Used for distinguishing variants, e.g. different post-processing like different holes, cuts, edges, ...
        volume = calculate_volume(context, resulting_o)
        volume = round(volume, context.scene.selection2bom_in_precision)
        if o.dupli_group:# and len(o.dupli_group.objects) > 0:
            cache_resolved_dupli_group_volume_map[o.dupli_group] = volume
    else:
        print("Neither dupli group to resolve nor supported object type for volume calculation for object: ", resulting_o, " type: ", resulting_o.type, " dupli group:", resulting_o.dupli_group)
    
    if volume != -1:
        # First encountered this entry volume variant?
        if not (bom_entry in bom_entry_variant_map.keys()):
            bom_entry_variant_map[bom_entry] = {}
            if debug:
                print('Keeping track of new variant/kind/post-processing of bom_entry ', bom_entry, ': volume: ', volume)
                
        if not (volume in bom_entry_variant_map[bom_entry].keys()):
            bom_entry_variant_map[bom_entry][volume] = 1
            # Generate blueprint:
            if context.scene.selection2bom_in_include_blueprints:
                if bpy.types.Scene.blueprint_settings:
                #    bpy.types.Scene.blueprint_settings.filelink = blueprint_filelink
                    blueprint_filelink_relative = build_blueprint_filelink(filelink, bom_entry, volume)
                    # Using the filelink relative to the open .blend file.
                    root = bpy.path.abspath('//')
                    blueprint_filelink = root + blueprint_filelink_relative 
                    print("blueprint filelink previous: ", context.scene.blueprint_settings.filelink)
                    filepath_old = context.scene.render.filepath
                    context.scene.render.filepath = blueprint_filelink
                    bpy.ops.scene.blueprint_filelink_set()
                    context.scene.render.filepath = filepath_old
                    print("blueprint filelink new: ", context.scene.blueprint_settings.filelink, " <- object: ", resulting_o, " type: ", resulting_o.type)
                    generate_engineering_drawing(context, resulting_o)
                else:
                    print("Error: Blender extension 'selection to blueprint' not installed or activated.")
        # Follow-up encounter of this postprocessed/volume variant of the entry:
        else:
            bom_entry_variant_map[bom_entry][volume] += 1
    
    # Resulting object no longer is required as volume is calculated and the engineering drawings are generated too.
    # TIDY UP:
    # Delete the join target if it is not the object that has to be resolved itself, which must be handled by the calling function that gave this object as a parameter to this function.
    if resulting_o != o:
        # delete it:
        bpy.ops.object.select_all(action='DESELECT')
        # still valid?
        if resulting_o:
            resulting_o.select = True
            print("deleting resulting_o after volume and blueprint calculations: ", resulting_o)
            bpy.ops.object.delete()
        
    
        

    # Keep track of how many BoM entries of same type have been found.
    count_map = bom_entry_count_map
    # In hybrid mode?
    if (context.scene.selection2bom_in_mode == '2'):
        # In hybrid mode the assemblies are listed separately.
        # Should not occur in the global parts lists if they are not atomar.
        if debug:
            print('==========> dupli_group: ', o.dupli_group)
        if (not (o.dupli_group is None) and len(o.dupli_group.objects) > 0):
            if debug:
                print('==========> is atomar: ', is_object_atomar(o))
            if (not is_object_atomar(o)):
                if debug:
                    print('Assembly found: ', o, '\r\n=> Putting into assembly_count_map.')
                count_map = assembly_count_map
            #else:
            #    # Both maps need to be incremented if atomar.
            #    increment_entry_in_map(bom_entry, assembly_count_map)
                
    increment_entry_in_map(bom_entry, count_map)

    # Have to add assembly entry?
    owning_group_instance_objects_length = len(owning_group_instance_objects)
        
    if (owning_group_instance_objects_length > 0):
    #for i in range(owning_group_instance_objects_length - 1, -1):
        # Important Note: The last item of the list could be spliced out! It's not done for performance. It's tested if for equality and skipped instead - in build_bom_entry().
        # Nevertheless if only one item is contained and it is the object itself, then a call to build_bom_entry() must be avoided because it else increments the variant count and thus also initiates the generation of another engineering drawing.
        parent_group_instance = None
        #if (owning_group_instance_objects_length > 0):
        parent_group_instance = owning_group_instance_objects[owning_group_instance_objects_length - 1]
        # Makes no sense to increment bom entry of an assembly if the assembly is the bom entry itself: 
        if owning_group_instance_objects_length > 1 or parent_group_instance != o:
            if debug:
                print('Assembly: Building bom entry ...')
            assembly_bom_entry = build_bom_entry(context, parent_group_instance, owning_group_instance_objects, filelink=filelink) #TODO store owning_group_instance_objects and iterate bottom up.
            # Keep track of how many BoM entries of the same type belong to this unique assembly:
            if (not (assembly_bom_entry in assembly_bom_entry_count_map)):
                if debug:
                    print('Assembly: From now on keeping track of assembly: ', assembly_bom_entry)
                assembly_bom_entry_count_map[assembly_bom_entry] = {}
                
            if (not (bom_entry in assembly_bom_entry_count_map[assembly_bom_entry])):
                if debug:
                    print('Assembly: From now on keeping track of bom_entry count of ', bom_entry)
                assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] = 0
        
            assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] += 1
            if debug:
                print('Assembly:', assembly_bom_entry, ' -> new part count: ', assembly_bom_entry_count_map[assembly_bom_entry][bom_entry], 'x ', bom_entry)
    
    print('----*done*,constructed and stored global Bill of materials and Assembly listing entries.')
    return bom_entry
    
    

def increment_entry_in_map(bom_entry, count_map):
    if (not (bom_entry in count_map)):
        if debug:
            print('From now on keeping track of bom_entry count of ', bom_entry)
        count_map[bom_entry] = 0
        
    count_map[bom_entry] = count_map[bom_entry] + 1
    if debug:
        print('-> new part count: ', count_map[bom_entry], 'x ', bom_entry)
    # To know how much compensating whitespace to insert later:
    is_longest_entry_count_then_store_len(count_map[bom_entry])  

    
 
#    
#g: bpy.types.Group not a group instance, i.e. no object with dupli group bpy.types.Group attached
def build_and_store_bom_entry_out_of_group(context, g):
    if debug:
        print('Encountered a group that should have been added to the BoM: ', g)
    #return build_and_store_bom_entry_out_of_group(context, g)
    return '\r\nBuilding bom entry out of group not supported yet. Possibly solve it analoguously to group instance dimension resolving.'


def deselect_all(context):
    if (not bpy.ops.object.select_all(action="DESELECT")):
        if debug:
            print('There seems to be already no selection - that may be interesting, but as we work with a copy it should not matter. Of importance is that now nothing is selected anymore.')
    if (context.scene.objects.active):  # Because join operator seems to weirdly join into the wrong target object (the logging output did show that everything was fine (i.e. joining into <o>.002 as expected ... and yet the joined object was <o>.001.
        context.scene.objects.active = None



#
# Constructing an entry for the bill of materials,
# i.e. figuring properties.
#
cache_resolved_dupli_group_dimensions_map = None
cache_resolved_dupli_group_volume_map = None
def build_bom_entry(context, o, owning_group_instance_objects, filelink=None, delete_join_result_if_differs=True):
    if debug:
        print('build_bom_entry: o:', o, ' owning_group_instance_objects:', owning_group_instance_objects)
    #build BoM entry: using http://www.blender.org/documentation/blender_python_api_2_69_release/bpy.types.Object.html
    entry = getBaseName(o.name)
    
    index = -1
    material = None
    if (o.active_material is None):
        if debug:
            print('Object ', o, ' has no active material.')
        if (not (o.dupli_group is None)):
            if debug:
                print('It\'s a dupli group attached to this object. => This is a group instance. => Resolving material from its objects.')
            share_same_material = True
            for group_object in o.dupli_group.objects:
                m = '-'
                if group_object.type == 'EMPTY':
                    continue
                if group_object.active_material:
                    m = getBaseName(group_object.active_material.name)
                #else:
                #    m = group_object.material_slots[0].material.name
                
                if material is None:
                    material = m
                else:
                    # Already met a material before - no matter if it was '-'.
                    if m != material:
                        share_same_material = False
                        material = 'MIXED'
                        break # can not take over a material other than 'mixed'.
                    
            if not share_same_material:
                print('Found no material shared by all attached group object members: ', o.dupli_group.objects)
    else:
        material = getBaseName(o.active_material.name)    #default value
        
    if material is None:# or material == 'transparent': # <- HACK: Because the material is changed to 'transparent' by the blueprint extension and not had been ensured to be restored - which is fixed in revision .
        material = '-'
        
    #look for a material explicitely specified:
    index = o.name.find('material:')
    if (index != -1):
        parts = o.name.split('material:')
        if (len(parts) > 1):
            material = parts[1]     #material given explicitely, e.g. Aluminium (Isotope XY)
        entry = parts[0]            
    else:
        index = o.name.find('Material:')
        if (index != -1):
            parts = o.name.split('Material:')
            if (len(parts) > 1):
                material = parts[1]
            entry = parts[0]
        else:
            index = o.name.find('mat:')
            if (index != -1):
                parts = o.name.split('mat:')
                if (len(parts) > 1):
                    material = parts[1]
                entry = parts[0]
            else:
                index = o.name.find('Mat:')
                if (index != -1):
                    parts = o.name.split('Mat:')
                    if (len(parts) > 1):
                        material = parts[1]
                    entry = parts[0]
                else:
                    index = o.name.find('M:')
                    if (o.name.find('M:') != -1):
                        parts = o.name.split('M:')
                        if (len(parts) > 1):
                            material = parts[1]
                        entry = parts[0]
                    else:
                        index = o.name.find('m:')
                        if (index != -1):
                            parts = o.name.split('m:')
                            if (len(parts) > 1):
                                material = parts[1]
                            entry = parts[0]
    
    # Remove indicators:
    atomar_indicator = 'atom'
    atomar_index = entry.find('' + atomar_indicator)
    if (atomar_index != -1):
        entry = re.sub(PATTERN_ATOM, '', entry)
        #parts = entry.split(atomar_indicator)
        #parts_length = len(parts)
        #if (parts_length > 1):
        #    #entry = parts[1]
        #    entry = ''
        #    # Reassemble, but skip the first part as it's the atomar indicator:
        #    for parts_index in range(1, parts_length):
        #        entry = entry + parts[parts_index]
        #        if parts_index < parts_length - 1:
        #            entry = entry + atomar_indicator
    indicator = 'optional'
    index = entry.find('' + indicator)
    if (index != -1):
        entry = re.sub(PATTERN_OPTIONAL, '', entry)
    
    # While optional and atomar indicator can be set per group instance object, the entry should be consistently using the dupli group name if available.
    # Otherwise entry counts of assemblies may be 0, 
    # if the group instance naming differs from the dupli group name.
    if o.dupli_group and o.dupli_group.name:
        if atomar_index != -1:
            print("build_bom_entry(): Atomar assembly entry uses dupli group name: ", o.dupli_group.name)
        else:
            print("build_bom_entry(): Assembly entry uses dupli group name: ", o.dupli_group.name)
        entry = getBaseName(o.dupli_group.name)
    

    #keep track of the longest material label
    is_longest_material_then_store_len(material_label=material)
    
    #dimensions
    context.scene.objects.active = o
    
    
    #######
    # DIMENSIONS
    #######
    # Dimension already takes dimension-influencing modifiers like array, skin, solidify into account (applying all modifiers is thus not required).
    # TODO don't take the absolute bounding_box dimensions - instead calculate from a hull of the object?
    
    #undo_count = 0 #now working with a copy of the initially selected_objects (no longer a live copy/reference)
    x = o.dimensions[0] # As it's in object context, the scale is taken into account in the bounding box already.
    y = o.dimensions[1]
    z = o.dimensions[2]
    # If provided inherit parent group instances' transforms:
    # If o owning_o equality and skip if equal (see performance hack, it's done to avoid removing element from the list which is live and still needed later).
        
    
    resulting_o = o
    
    global cache_resolved_dupli_group_dimensions_map
    if o.dupli_group and o.dupli_group in cache_resolved_dupli_group_dimensions_map:
        if debug:
            print('Skipping time costly resolving due to dupli group dimensions cache ... (for an environmental friendly planet)')
        x = cache_resolved_dupli_group_dimensions_map[o.dupli_group][0]
        y = cache_resolved_dupli_group_dimensions_map[o.dupli_group][1]
        z = cache_resolved_dupli_group_dimensions_map[o.dupli_group][2]
        
    elif (not (o.dupli_group is None) and len(o.dupli_group.objects) > 0):

        #if debug:
        print('o ', o, ' dupli_group: ', o.dupli_group)
        context.scene.objects.active = o
        bpy.ops.object.resolve_and_join()
        resulting_o = context.scene.objects.active
        
        print('Adopting total dimensions of the complete assembly (joined): ', context.scene.objects.active)    
        # Inherit the dimensions. 
        x = context.active_object.dimensions[0]
        y = context.active_object.dimensions[1]
        z = context.active_object.dimensions[2]
        cache_resolved_dupli_group_dimensions_map[o.dupli_group] = resulting_o.dimensions.copy()  # <-- Can't store the reference as this object is just temporary. Might require recheck of validity, though such invalidation while executing the selection2bom script is impossible in blender as of now (check revision time) because the objects can't be manipulated while the operator (addon) is executing.
    #else: # no dupli group.
         
         
    # Duplicates_make_real already makes the resulting objects inherit the scale! If that ever changes, then enable the following commented lines that then would be required for group instances/empties only, because the dimensions of mesh and curve objects already include the scale. Thus both when the dupli group is resolved and when its dimension is read from the cache - then the group instance's scale needs to be applied (if duplicates_make_real operator functionality no longer takes scale into account):
    #if o.dupli_group:
    #    # Apply scale of this (empty) object as it might be scaled itself:
    #    x *= o.scale[0]
    #    y *= o.scale[1]
    #    z *= o.scale[2]
    #    x *= o.delta_scale[0]
    #    y *= o.delta_scale[1]
    #    z *= o.delta_scale[2]
       
    
    
    # Apply inherited delta transforms:    
    owning_group_instance_objects_length = len(owning_group_instance_objects)
    owning_group_instance_objects_index = owning_group_instance_objects_length - 1
    is_optional = False
    # The rotation is no longer cancelled out, thus the inverted matrices must be chained/multiplied:
    rotation_matrix = o.matrix_basis.to_3x3()#Matrix([1, 0, 0], [0, 1, 0], [0, 0, 1])
    while owning_group_instance_objects_index > -1:
        #print('index: ', owning_group_instance_objects_index, ' of length ', owning_group_instance_objects_length)
        owning_group_instance_object = owning_group_instance_objects[owning_group_instance_objects_index]
        # The object o itself might reside at the last position in the list, for performance reasons it was not removed. So skip it:
        if (owning_group_instance_object != o):
            # The object itself or any of the previous owning group instance objects may be rotated, so either this rotation must be cleared or the rotation must be taken into account:
            
            # Rotate back, i.e. invert the rotation:
            # NOTE Either left or right multiplication is chosen randomly here.
            ogio_scale = rotation_matrix * owning_group_instance_object.scale
            ogio_delta_scale = rotation_matrix * owning_group_instance_object.delta_scale
            
            #owning_group_instance_object.rotation_euler = ogio_rotation_euler_to_restore
            
            # Print results:
            print('object scale: ', owning_group_instance_object.scale, ' -> rotation inverted scale: ', ogio_scale)
            print('object delta_scale: ', owning_group_instance_object.delta_scale, ' -> rotation inverted scale: ', ogio_delta_scale)
            
            x *= ogio_scale[0]
            y *= ogio_scale[1]
            z *= ogio_scale[2]
            x *= ogio_delta_scale[0]
            y *= ogio_delta_scale[1]
            z *= ogio_delta_scale[2]
            
            rotation_matrix *= owning_group_instance_object.matrix_basis.to_3x3()
            
           
        if (is_object_optional(owning_group_instance_object)):
            is_optional = True
          
        owning_group_instance_objects_index -= 1


    #determine units using the unit scale of the scene's unit/world settings
    dimensions = [
            getMeasureString(x, context.scene.unit_settings, context.scene.selection2bom_in_precision),
            getMeasureString(y, context.scene.unit_settings, context.scene.selection2bom_in_precision),
            getMeasureString(z, context.scene.unit_settings, context.scene.selection2bom_in_precision),
    ]
    
    
    
    #undo - restore the modifiers #if no active object then no modifiers have been applied hence nothing to be undone.
    #if ( not (context.active_object is None) and not (result == {'CANCELLED'}) ):
    #    operations_undone_count = 0
    #    while (operations_undone_count < operations_to_undo_count): 
    #        result = bpy.ops.ed.undo()#undo_history()
    #        if (result):
    #            operations_undone_count = operations_undone_count + 1
    #    if debug:
    #        print('operations_undone count: ', operations_undone_count)
        
    bom_entry = entry + '___' + material + '___[' + dimensions[0] + ' x ' + dimensions[1] + ' x ' + dimensions[2] + ']___'
    if (is_optional):
        bom_entry = bom_entry + '1'
    #else:
    #    bom_entry = bom_entry + '0'
        
    #NOT RELEVANT: + '\t \t[object is in group: ' o.users_group ', in Scenes: ' o.users_scene ']'
    
    
    #######
    # VOLUME VARIANTS (as independent additional information)
    #######
    #global cache_resolved_dupli_group_volume_map
    # Note: When generating the quantitieslist, the keys of the variant map are read
    #       to determine the volume variants. With the volume known, the filelink to
    #       the corresponding generated blueprint can be assembled and the count and
    #       images of the variants included in the BOM.
    volume_bounding_box = x * y * z
    # NOTE The effort to calculate the real volume has been moved to the calling function because volume currently is not included in the bom entry directly. 
    
    # NOTE The calling function is responsible for deleting the join result if the join result is still needed afterwards, which may not be intuitive, nevertheless currently is required due to technical reasons (namely allowing this function to be called for assembly entry generation without having it to generate engineering drawings, volume again and again).
    if not delete_join_result_if_differs:
        context.scene.objects.active = resulting_o
        return bom_entry
    
    # TIDY UP:
    # Delete the join target if it is not the object that has to be resolved itself, which must be handled by the calling function that gave this object as a parameter to this function.
    if resulting_o != o:
        # delete it:
        bpy.ops.object.select_all(action='DESELECT')
        # still valid?
        if resulting_o:
            resulting_o.select = True
            print("deleting resulting_o: ", resulting_o)
            bpy.ops.object.delete()
        
    return bom_entry



class OBJECT_OT_ResolveRecursively(bpy.types.Operator):
    """Resolves dupli group/ instance / assembly recursively."""
    #=======ATTRIBUTES=========================================================#
    bl_idname = "object.resolve_recursively"
    bl_label = "Resolve recursively"
    bl_context = "objectmode"
    bl_register = True
    bl_undo = True
    #bl_options = {'REGISTER', 'UNDO'}
    
    #=======CONSTRUCTION=======================================================#
    #def __init__(self):
    #=======METHODS============================================================#
    @classmethod
    def poll(self, context):
        # check the context:
        return context.scene and context.scene.objects.active

    #
    # Command base function (outline).
    #
    def execute(self, context):
        time_start = time.time()
        #print("Storing selected objects ...")
        #selected_objects = list(context.selected_objects)
        
        print("Initiating resolve of %s ..." % context.scene.objects.active)
        objects_to_be_deleted = []
        objects_to_be_joined = []
        
        resolve_all_joinable_objects_recursively(context, context.scene.objects.active, objects_to_be_joined, objects_to_be_deleted)
        # TODO As resolving group instances recursively is costly, it would be nice to use more of the info gained. 
        # TODO When to apply modifiers?
        print("*done* Resulting objects: ", objects_to_be_joined)
        # Tidy up:
        print("Tidying up ...")
        delete_objects(context, objects_to_be_deleted, exceptions=context.selected_objects)
        
        #print("Restoring selected objects ...")
        #bpy.ops.object.select_all(action='DESELECT')
        #for o in selected_objects:
        #   o.select = True
        #print("*done*")
        
        # Ensure nothing is selected:
        deselect_all(context)
        # Select the joined objects:
        for o in objects_to_be_joined:
            o.select
        
        print("Resolve finished, required: %.4f sec" % (time.time() - time_start))
        return {'FINISHED'}



class OBJECT_OT_ResolveAndJoin(bpy.types.Operator):
    """Resolves dupli group/ instance / assembly recursively. Then joins all objects into one which then is available as active object."""
    #=======ATTRIBUTES=========================================================#
    bl_idname = "object.resolve_and_join"
    bl_label = "Resolve and join"
    bl_context = "objectmode"
    bl_register = True
    bl_undo = True
    #bl_options = {'REGISTER', 'UNDO'}
    
    #=======CONSTRUCTION=======================================================#
    #def __init__(self):
    #=======METHODS============================================================#
    @classmethod
    def poll(self, context):
        # check the context:
        return context.scene and context.scene.objects.active

    #
    # Command base function (outline).
    #
    def execute(self, context):
        time_start = time.time()
        
        print("Initiating resolve of %s and join ..." % context.scene.objects.active)
        objects_to_be_deleted = []
        objects_to_be_joined = []
        object_to_resolve = context.scene.objects.active
        resolve_and_join(context, object_to_resolve, objects_to_be_joined, objects_to_be_deleted)
        resulting_object = context.scene.objects.active
        print("*done* Resulting object: ", resulting_object)
        # Tidy up:
        print("Tidying up ...")
        #leads to segmentation fault probably to missing pointer validity check in 'to string' function: print("Deleting objects: ", objects_to_be_deleted, " exceptions: ", objects_to_be_joined)
        bpy.ops.object.select_all(action='DESELECT')
        for o in objects_to_be_deleted:
            if o in objects_to_be_joined:
                print('Skipping object to be deleted because it may (rather should) have been joined: ', o)
                continue
            # Let the decision about when to delete the join target/resulting object and the original object (note if the original object is of type MESH and the join objects are mesh too (or all are CURVE objects consistently), then the resulting object may be the object to resolve (this is currently prevented in code, but it may be at a later point both be allowed to join curves too and to let the object to be resolved be the join target at the same time. Also note the object to be resolved is duplicated before it is resolved/made real.).
            if o == resulting_object or o == object_to_resolve:
                print("Skipping object to be deleted because it is the resulting object or initial object to resolve.")
                continue
            if o:
                o.select = True
        print(context.selected_objects, " active: ", context.active_object)
        if len(context.selected_objects) > 0:
            print("Deleting ...")
            bpy.ops.object.delete()
        print("*done*")
        
        print("Resolve and join finished, required: %.4f sec" % (time.time() - time_start))
        return {'FINISHED'}




def resolve_and_join(context, o, objects_to_be_joined=[], objects_to_be_deleted=[]):
    
    resolve_all_joinable_objects_recursively(context, o, objects_to_be_joined, objects_to_be_deleted)
    
    # Ensure nothing is selected:
    deselect_all(context)
    
    # TODO As resolving group instances recursively is costly, it would be nice to use more of the info gained. 
    # TODO When to apply modifiers?
    
    objects_to_be_joined_length = len(objects_to_be_joined)
    if objects_to_be_joined_length > 0:
        for objects_to_be_joined_index in range(0, objects_to_be_joined_length):
            object_to_be_joined = objects_to_be_joined[objects_to_be_joined_index]
            object_to_be_joined.select = True
            apply_modifiers(context, object_to_be_joined)
        
        # Arbitrarily choose the last object as target:
        context.scene.objects.active = objects_to_be_joined[objects_to_be_joined_length - 1]
        if debug:
            print(context.selected_objects, '\r\nactive_object: ', context.active_object)
            print('joining ...')
        # Attention: Poll may fail because a context of joining into an empty is not valid!
        if (not bpy.ops.object.join()):
            print('Joining the temporary selection (all group instances within this group instance duplicated, made real and its dupli groups\' objects recursively treated the same too) failed. Check for unjoinable object types.')
            #break
        #else:
        #    if context.active_object and (not context.active_object == o):
        #        objects_to_be_deleted.append(context.scene.objects.active)
        if (not context.scene.objects.active):
            print('WARNING: Active object not set after join operation.')
        else:
            context.scene.objects.active.select = True
    else:
        print('WARNING: Might have found nothing to join ...')
        # TODO Use the dimension of the greatest object within its dupligroup (this includes CURVE objects). Only adopt if greater than the currenty evaluated object's dimensions.
        o.select = True # If the above functionality isn't, then this may be simplified. This is obsolete as it's the default dimension anyway.
        context.scene.objects.active = o
    return context.scene.objects.active



def generate_engineering_drawing(context, obj):
    print("-Generate engineering drawing. obj: ", obj)
    global execution_round
    execution_round += 1
    #if execution_round > execution_round_max:
    #    raise Error
    active_old = context.scene.objects.active
    bpy.ops.object.select_all(action='DESELECT')
        
    context.scene.objects.active = obj
    obj_select = obj.select
    obj.select = True
    #print("active old: ", active_old, " obj: ", obj, " select: ", obj.select)
    #print("selected_objects: ", context.selected_objects)
    context.scene.objects.active.select = True
    bpy.ops.object.mode_set(mode='OBJECT')
    # Invoke operator of selection2blueprint addon:
    bpy.ops.object.selection2blueprint()
    obj.select = obj_select
    
    # restore active object:
    context.scene.objects.active = active_old
    
    print(execution_round, " x generate engineering drawing for BoM finished")

execution_round = 0
execution_round_max = 2

#
# NOTE Please give the obj parameter as duplicate object because
# it will be made single user, which will change the overall object,
# data relations and is not recommended if the object is needed later.
#
def apply_modifiers(context, obj):
    active_old = context.scene.objects.active
    #selection_old = list(context.selected_objects)
    #bpy.ops.object.select_all(action='DESELECT')
    context.scene.objects.active = obj
    
    # Because multi-user mesh does not allow applying modifiers:
    if not (bpy.ops.object.make_single_user(object=True, obdata=True)):#, material=True, texture=True, animation=True)):
        print("apply_modifiers(): Could not make obj %s single user object, data.", obj)
        return 
    
    # apply modifiers from top to bottom:
    modifier_count = len(obj.modifiers)
    modifiers_index = 0
    object_to_layers_to_restore_map = {}
    while (modifiers_index < modifier_count):
        m = obj.modifiers[modifiers_index]
        print('Applying modifier: ', m)
        if hasattr(m, "object"):
            #print(' object: ', m.object)
            object_to_layers_to_restore_map[m.object] = m.object.layers # Copying should not be required, because the object still exists at the memory address and no matter if the memory where the layers variable is pointing to is changed, the map value still bears the old memory address, which thus stays in memory. Copying would just add clutter which had to be garbage collected.
            m.object.layers = obj.layers#<- not copying because the pointer is overridden immediately again, which prevents unintentional side effects which'd be major reason for copying. list(obj.layers)
            #for l_i in range(0, len(m.object.layers)):
            #    m.object.layers[l_i] = True
            #NOT CERTAIN THAT THIS OBJECT HAS BEEN ADDED, ONLY SCRIPT-ADDED THINGS ARE REMOVED AGAIN. if m.object.type == 'MESH':
            #    objects_to_be_deleted.append(object_for_intersection)
        #if hasattr(m, "operation"):
        #    print(' operation: ', m.operation)
        bpy.ops.object.modifier_apply(apply_as='DATA',modifier=m.name)
        #modifiers_index += 1 <- because the others are shifted upwards.
        modifier_count -= 1
        
    # Restoring layer configuration ...
    for o, layers in object_to_layers_to_restore_map.items():
        o.layers = layers
    
    context.scene.objects.active = active_old



def calculate_volume(context, obj):
    objects_to_be_deleted = []
    if obj.type != 'MESH':
        print("Calculation of volume not (yet) supported for object of type: ", obj.type)
        return -1
    print("calculating volume of object %s ..." % obj)
    active_old = context.scene.objects.active
    #selection_old = list(context.selected_objects)
    bpy.ops.object.select_all(action='DESELECT')
    context.scene.objects.active = obj
    context.scene.objects.active.select = True
    bpy.ops.object.duplicate()
    obj_duplicate = context.scene.objects.active
    objects_to_be_deleted.append(obj_duplicate)
    
    apply_modifiers(context, obj_duplicate)
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False) 
    bpy.ops.mesh.quads_convert_to_tris(quad_method='FIXED', ngon_method='CLIP')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    mesh = obj.data
    print("Polygons: ", mesh.polygons) # since 2.62
    #print("Tesselated faces:", obj.data.tessfaces) # often out of sync
    volume = 0
    for f in mesh.polygons:
        if len(f.vertices) > 3:
            print("Warning: Face is not a triangle after triangulation: ", f.index)
        a = mesh.vertices[f.vertices[0]].co
        b = mesh.vertices[f.vertices[1]].co
        c = mesh.vertices[f.vertices[2]].co
        da = a[0] * (c[1] - b[1])
        db = b[0] * (a[1] - c[1])
        dc = c[0] * (b[1] - a[1])
        
        dV = (a[2] + b[2] + c[2]) / 3.0 * .5 * abs(da + db + dc)
        sign = 0
        if f.normal[2] < 0:
            sign = -1
        elif f.normal[2] > 0:
            sign = 1
        #print("sign: ", sign, " dV: ", dV, " f.normal: ", f.normal)
        volume += sign * dV
        
    print("*done* Volume: ", volume)
    
    delete_objects(context, objects_to_be_deleted)
    
    context.scene.objects.active = active_old
    return abs(volume)


def delete_objects(context, objects_to_be_deleted, exceptions=[]):
    # Ensure nothing is selected:
    if (len(context.selected_objects) > 0):
        deselect_all(context)
        
    # Select all objects that still have to be deleted (all but the joined ones):    
    objects_to_be_deleted_length = len(objects_to_be_deleted)
    if (objects_to_be_deleted_length > 0):
        for objects_to_be_deleted_index in range(0, objects_to_be_deleted_length):
            o = objects_to_be_deleted[objects_to_be_deleted_index]
            if o and (not (o in exceptions)):
                o.select = True
        if debug:
            print(context.selected_objects, '\r\nactive_object: ', context.active_object)
            print('deleting ...')
        bpy.ops.object.delete()
    


def resolve_all_joinable_objects_recursively(context, o, objects_to_be_joined, objects_to_be_deleted, is_already_duplicate=False, recursion_depth=0):
    #print(str(recursion_depth) + 'resolve_all_joinable_objects_recursively: o: ',o, ' to_be_joined: ', objects_to_be_joined, ' objects_to_be_deleted: ', objects_to_be_deleted)
    if (recursion_depth > context.scene.after_how_many_create_bom_entry_recursions_to_abort):
        print(str(recursion_depth) + ' Reached recursion depth limit: ', context.scene.after_how_many_create_bom_entry_recursions_to_abort, ' current recursion depth: ', recursion_depth)
        return {'FINISHED'}
    
    # Ensure nothing is selected:
    deselect_all(context)
    
    #undo_count = undo_count + 1
    o.select = True
    #undo_count = undo_count + 1
    
    #BELOW THIS LINE NOTHING HAS TO BE UNDONE! AS THIS DUPLICATED OBJECT
    #(GROUP INSTANCE) WILL SIMPLY BE DELETED AFTERWARDS.
    if (not is_already_duplicate): #<-- it may be duplicated, but make_real seems to duplicate linked!
        if (not bpy.ops.object.duplicate(linked=False)):#non-linked duplication of selected objects
            print('Object to be resolved not yet is duplicate, but duplicate() operator failed')
        else:
            bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)
    
    if (len(context.selected_objects) > 1):
        print('Only one object (the group instance or one of the objects within its group) should have been selected.\r\nSelection: ', context.selected_objects, '. Thus dimension will only reflect those of the dupli group objects of the first selected group instance object.')
    elif (len(context.selected_objects) < 1):
        print('Warning: It was no object selected but exactly one object should have been selected.\r\nSelection: ', context.selected_objects, '.')
    context.scene.objects.active = context.selected_objects[0]
    
    # The new (copy) group instance hopefully is the active object now:
    if (not context.scene.objects.active):
        print('Warning: No active object after duplicating object: ', o)
    else:
        if debug:
            print('active object after duplication of group instance: ', context.active_object, ' or :', context.scene.objects.active)
            
    o_duplicate = context.scene.objects.active
   
    # If the objects are duplicated, then they still are in the same groups as the original object. This means the dupli_group suddenly has more members, which leads to endless recursion. Thus remove the duplicates from all groups:
    #if debug:
    #    print('Removing selected objects from all groups. ', context.selected_objects)
    #for selected_duplicate in context.selected_objects:
    #    for d_group in selected_duplicate.users_group:
    #        bpy.ops.group.objects_remove(group=d_group)
    bpy.ops.group.objects_remove_all()
    
    # As this is a duplicate, it needs to be removed later on:
    # Required because of joining only allows mesh or curve only - no mix!
    if (context.scene.objects.active.type == 'MESH'):
        # No need to delete the object because it is joined, which also removes it if it's not the join target.
        objects_to_be_joined.append(o_duplicate)
    else:
        objects_to_be_deleted.append(o_duplicate) # It's safer here as joining into an active object keeps up the active object of course. Thus the object should be deleted but it is not as it has been marked for join. Thus better not even mark for deletion.

    # Further decomposition possible? 
    if (not (o_duplicate.dupli_group is None)):
        # Store a reference because it's not certain that an operator not changes the active object.
        group_instance_object = o_duplicate
        if debug:
            print('Making real ... active: ', context.scene.objects.active) 
        #the active object (group instance) should be the only selected one:
        group_instance_object.dupli_type = 'GROUP' # Turned the function into an operator, then a bug appeared: the dupli_type was cleared, somehow set to None.
        bpy.ops.object.duplicates_make_real(use_base_parent=True)#false because we don't set up
                #the empty group instance as parent of the now copied and no longer referenced group objects!
                #The dupli group attached to this object
                #is copied here as real value object copies (not references). Though as it's apparently linked,
                #making single user is required:
        print('Making single user ... selected objects: ', context.selected_objects)   
        bpy.ops.object.make_single_user(type='SELECTED_OBJECTS', object=True, obdata=True)
        #Note:
        # The real objects (including the group instance's empty!) that now reside where the group instance was before
        # should already be selected after duplicates_make_real. (Note while make_real resolves to the very bottom,
        # this (our) algorithm also works if this feature should change in the future as it's a recursive approach.)
        if (len(context.selected_objects) < 1): 
            print('Attention: No selection after duplicates_make_real operator! active object: ', context.scene.objects.active)
        
        bpy.ops.group.objects_remove_all() # optional (because make_real removes the objects from all groups already)
            
        #group_objects = context.scene.objects.active.dupli_group.objects#.children
        group_objects = context.selected_objects
        #selected_objects_count = 0
        for group_object in group_objects:
            # If EMPTY is a considered type, then the empty corresponding to the current object (that also resides after duplicates_make_real) must be skipped:
            if (group_object == group_instance_object): # the 'is' operator does not work here.
                if debug:
                    print('>> Skipping group object %s because it\'s the group instance object %s itself.' % (group_object, group_instance_object))
                continue
            if (not is_object_type_considered(group_object.type)):
                print ('Warning: Group object\'s type is not considered.')
                objects_to_be_deleted.append(group_object)
                continue
            resolve_all_joinable_objects_recursively(context, group_object, objects_to_be_joined, objects_to_be_deleted, is_already_duplicate=True, recursion_depth=(recursion_depth + 1))
            #++selected_objects_count
        
    return {'FINISHED'}


 

#
# White space for filling up to a certain length.
#
def getWhiteSpace(count):
    return getCharInstances(' ', count)

def getCharInstances(char, count):
    if (count < 1):
        return ''
    count = int(round(count, 0))
    chars = ''
    for i in range(0, count): # range() is exclusive at the upper bound.
        chars = chars + char
    return chars

#
#
#
def processEntry(entry, column_separator=""):
    entry_parts = entry.split('___')
    label = entry_parts[0]
    material = entry_parts[1]
    dimensions = entry_parts[2]
    is_optional = entry_parts[3]
    
    whitespace_count = object_longest_label_len - len(label)
    material_whitespace_count = material_longest_label_len - len(material)
    if debug:
        print('object whitespace count: ', whitespace_count, '\t material whitespace count: ', material_whitespace_count)
    
    pre = ''
    post = ''
    if (is_optional):
        pre = ''#PREPEND_IF_OPTIONAL
        post = APPEND_IF_OPTIONAL
    entryProcessed = '\t' + pre + label + getWhiteSpace(whitespace_count) + '\t' + column_separator + material + getWhiteSpace(material_whitespace_count) + '\t' + column_separator + dimensions + post;
    #entryProcessed_len = len(entryProcessed)
    
    return entryProcessed



#
# All found bom entries are written to a file.
#
PREPEND_IF_OPTIONAL = '('
APPEND_IF_OPTIONAL = ')'
def write2file(context, bom_entry_count_map, bom_entry_info_map, assembly_count_map, assembly_bom_entry_count_map, filelink=None):#<-- argument is a dictionary (key value pairs)!
    if debug:
        print('Writing bill of materials to file ...')
        
    if (filelink is None):
        filelink = build_filelink(context)
    if debug:
        print('Target filelink: ', filelink)
        print('Highest entry count string char count: ', entry_count_highest_digit_count)
        print('Highest object label char count: ', object_longest_label_len)
        print('Highest material char count: ', material_longest_label_len)
        
    #write to file
    result = False
    with open(filelink, 'w') as f:#for closing filestream automatically
        #f.read()
        #f.readhline()
        
        # HTML / Markdown additions:
        table_begin = ""
        
        header_begin = ""
        header_row_begin = ""
        header_column_separator = ""
        header_row_end = ""
        header_end = ""
        
        body_begin = ""
        row_begin = ""
        column_separator = ""
        column_separator_colspan_remainder = ""
        row_end = ""
        row_empty = ""
        body_end = ""
        
        table_end = ""
        if (context.scene.selection2bom_in_include_blueprints):
            # Add html markup per entry: <tr><td></td></tr> or <td colspan="3"></td> if blueprint/image row.
            table_begin = "<table>"
        
            header_begin = "<thead>"
            header_row_begin = "<tr><th>"
            header_column_separator = "</th><th>"
            header_row_end = "</th></tr>"
            header_end = "</thead>"
        
            body_begin = "<tbody>"
            row_begin = "<tr><td>"
            column_separator = "</td><td>"
            column_separator_colspan_remainder = '</td><td colspan="3">'
            row_end = "</td></tr>"
            row_empty = '<tr><td colspan="4"></td></tr>'
            body_end = "</tbody>"
        
            table_end = "</table>"
        
        bom = table_begin
        bom += header_begin
        bom += header_row_begin + getWhiteSpace(entry_count_highest_digit_count) + '#  \t' + header_column_separator + 'Label' + getWhiteSpace(object_longest_label_len - 5) + '\t' + header_column_separator + 'Material ' + getWhiteSpace(material_longest_label_len - 8) + '\t' + header_column_separator + 'Dimensions' + header_row_end
        if not context.scene.selection2bom_in_include_blueprints:
            bom = bom + '\r\n'
            bom = bom + getWhiteSpace(entry_count_highest_digit_count) + '-  \t-----' + getWhiteSpace(object_longest_label_len - 5) + '\t---------' + getWhiteSpace(material_longest_label_len - 8) + '\t----------'
        bom = bom + '\r\n'
        bom += header_end
        
        bom += body_begin
        bom += row_empty
        # Total part (counts):
        for entry, entry_count in bom_entry_count_map.items(): 
            pre = ''
            if (entry.split('___')[3] != ''):
                pre = PREPEND_IF_OPTIONAL
            digit_count = len(str(entry_count) + pre)
            whitespace_count = entry_count_highest_digit_count + len(PREPEND_IF_OPTIONAL) - digit_count
            bom = bom + '\r\n' + row_begin + pre + getWhiteSpace(whitespace_count) + str(entry_count) + 'x ' + column_separator + processEntry(entry, column_separator)
            bom += row_end
            
            # Include extra information line?
            if context.scene.selection2bom_in_include_info_line:
                if entry in bom_entry_info_map:
                    entry_information = '\r\n' + row_begin + getWhiteSpace(entry_count_highest_digit_count + len(PREPEND_IF_OPTIONAL) + len('x ')) + '\t' + column_separator_colspan_remainder + bom_entry_info_map[entry]
                    bom = bom + entry_information + row_end
                    #price_and_annotation = '\t' + getCharInstances('_', (entry_count_highest_digit_count + 2 + object_longest_label_len + material_longest_label_len)) #+ object_longest_dimension_string_length
                else:
                    if debug:
                        print('No information for entry: ', entry)
                    
            # Include blueprints (1 per variant)?
            if (context.scene.selection2bom_in_include_blueprints):
                if entry in bom_entry_variant_map:
                    for variant_volume, variant_count in bom_entry_variant_map[entry].items():
                        blueprint_filelink = build_blueprint_filelink(filelink, entry, variant_volume)
                        blueprint = '<img src="'+ blueprint_filelink +'" title="Volume: ' + str(variant_volume) + '" alt="blueprint"/>' 
                        head = '\r\n' + row_begin + getWhiteSpace(entry_count_highest_digit_count - len(str(variant_count)) + len(PREPEND_IF_OPTIONAL)) + str(variant_count) + 'x \t' + column_separator_colspan_remainder + blueprint #+ variant_volume
                        #body = '\r\n' + getWhiteSpace(entry_count_highest_digit_count + len(PREPEND_IF_OPTIONAL) + len('x ')) + '\t' + blueprint
                        bom = bom + head + row_end
                else:
                    if debug:
                        print('No variants for entry: ', entry)
                
                
            bom = bom + '\r\n' + row_empty # <- Some space for clearly structuring by which entries belong together.
        #bom = bom + '\r\n'
        bom += body_end
        
        bom += body_begin
        # Assemblies (including count):
        if (context.scene.selection2bom_in_mode == '2'):
            bom = bom + '\r\n\r\n\r\n======= ASSEMBLIES: ======'
            for assembly, entry_count_map in assembly_bom_entry_count_map.items(): 
                # Skip atomar assemblies (as they are listed in the global list and not to be decomposed):
                if (not (assembly in assembly_count_map)):
                    if (not (assembly in bom_entry_count_map)):
                        print('Assembly neither found in assembly count map nor in global bom entry count map.')
                    if debug:
                        print('Skipping atomar assembly: ', assembly)
                    continue 
                # it's a decomposable assembly, i.e. a non-empty and non-atomar one:   
                bom = bom + '\r\n--------------'
                pre = ''
                if (assembly.split('___')[3] != ''):
                    pre = PREPEND_IF_OPTIONAL
                assembly_count = assembly_count_map[assembly]
                digit_count = len(str(assembly_count) + pre)
                whitespace_count = entry_count_highest_digit_count + len(PREPEND_IF_OPTIONAL) - digit_count
                bom = bom + '\r\n' + row_begin + pre + getWhiteSpace(whitespace_count) + str(assembly_count) + 'x ' + column_separator + processEntry(assembly, column_separator) + ':'
                bom += row_end

                bom = bom + '\r\n-------'
                for entry, entry_count in entry_count_map.items(): 
                    pre = ''
                    if (entry.split('___')[3] != ''):
                        pre = PREPEND_IF_OPTIONAL 
                    count_string = str(int(round(entry_count/assembly_count, 0)))# + '(' + str(entry_count) + ')')
                    print(count_string, " = entry_count: ", entry_count, " / assembly_count: ", assembly_count)
                    digit_count = len(count_string + pre)
                    whitespace_count = entry_count_highest_digit_count + len(PREPEND_IF_OPTIONAL) - digit_count
                    bom = bom + '\r\n' + row_begin + pre + getWhiteSpace(whitespace_count) + count_string + 'x ' + column_separator + processEntry(entry, column_separator)
                    bom += row_end
                    #bom = bom '\r\n'
                    
                bom = bom + '\r\n' + row_begin + '--------------\r\n\r\n' + column_separator_colspan_remainder + '' + row_end
                  
        bom += body_end
            
            
        result = f.write(bom)
        if (result):
            print('Bill of materials created: ', filelink)
        else :
            print('Bill of materials: creation failed! ', filelink)
    return result
        


def build_blueprint_filelink(filelink, entry, variant_volume):
    root = bpy.path.abspath('//')
    filelink_relative_to_blend = filelink.replace(root, '')
    if filelink_relative_to_blend.startswith('/'):
        filelink_relative_to_blend = '.' + filelink_relative_to_blend#.replace('^/', '')
    print(filelink_relative_to_blend)
    
    # TODO This filelink might be too long for most filesystems.
    blueprint_filelink = filelink_relative_to_blend + '__entry_' + entry.replace(' ', '_').replace('[', '').replace(']', '') + '__volume_' + str(variant_volume) + '__blueprint.jpg'

    return blueprint_filelink
    


# This bom entry is appended to a file.
def append_bom_entry_to_file(context, bom_entry):
  return append_to_file(context, '\r\n' + str(bom_entry_count_map[bom_entry]) + 'x ' + bom_entry)
  
  
def append_to_file(context, content):
    
    if debug:
        print('Target filelink: ', filelink)
        
    #append to file
    with open(filelink, 'a') as f:#for closing filestream automatically
        #f.read()
        #f.readhline()
        if (f.write(content)):
            print('Appended to file: ', filelink, ' \t Content: ',  content)
            return True
        
        #f.tell()
        #f.seek(byte) #e.g. 0123 -> 4th byte is 3
        #http://docs.python.org/3/tutorial/inputoutput.html
    #f.close() -- no longer necessary when using with/scope
    #use pickle.dump(object, filestream) and pickle.load(filestream) (somewhat like serialization?)
    return False



#
# Construct a valid output filelink.
# Prepend may be useful for giving a context, e.g. to group the file with a scene it belongs to.
# Or e.g. to group blueprints with a Bill of materials.
#
def build_filelink(context, prepend=''):
    if debug:
        print('Building filelink ...')

    # Build filelink:
    root = bpy.path.abspath('//')
    if (root == ''):
        if debug:
            print('.blend File not saved yet. Storing BOM to HOME or current directory.')
        root = './'#using relative paths -> to home directory
        #root = os.getcwd()#<-- current working directory, so where the blender was launched from.
    print('Root: ' + root)
    #root = dirname(pathname(__FILE__))#http://stackoverflow.com/questions/5137497/find-current-directory-and-files-directory
    filename = prepend + 'BoM-' # TODO How to determine this blend file's name?
    fileending = '.txt'
    if context.scene.selection2bom_in_include_blueprints and hasattr(context.scene, "blueprint_settings"):
        fileending = '.md' # Markdown format for showing images directly on the git mirror, e.g. Github. Though html also works because the syntax is html.
        
    #objectname = getBaseName(context.selected_objects[0].name)
    objectname = None
    if context.active_object:
        objectname = getBaseName(context.active_object.name)
    if context.scene.name:
        objectname = context.scene.name
    if (not objectname or objectname is None):
        objectname = 'neither_active_object_nor_scene_name'
    
    filename = filename + objectname
    filelink = root + '/' + filename + fileending
    
    # Don't overwrite existing files because for several subsequent selections made,
    # individual (and persisting) files could be desired.
    number = 0
    while (os.path.isfile(filelink)):#alternatively: try: with (open(filelink)): ... except IOError: print('file not found') 
        number = number + 1              #http://stackoverflow.com/questions/82831/how-do-i-check-if-a-file-exists-using-python
        filename_ = filename + str(number)
        filelink = root + '/' + filename_ + fileending

    # A non-existant filelink was found.
    return filelink






#HELPER - TIDYUPNAMES
def tidyUpNames():
    ############
    #fetch active object
    ############
    active_obj = isThereActiveObjectThenGet(context)
    if (not active_obj or active_obj is None):
        if debug:
            print('Aborting tidying up names because there is no active object.'
            ' So nothing was left after the joining or grouping?')
        return False
    ############
    #tidy up - dismiss the .001, .002, .. endings if necessary
    ############
    if debug:
        print('Object-name before refactoring: ', active_obj.name)
    cleanname = getBaseName(active_obj.name)
    if (cleanname and cleanname != active_obj.name):
        if debug:
            print('renaming')
        active_obj.name = cleanname
        if debug:
            print('renaming *done*')
    #debug
    if debug:
        print('Object-name after refactoring: ', active_obj.name)
    return True




#
# Helper for checking if a selection is made and retrieving it (for single source principle).
#
def isThereSelectionThenGet(context):
    #opt. check if selection only one object (as is to be expectat after join)
    sel = context.selected_objects
    if (debug):
        print('Count of objects in selection (hopefully 1): ', len(sel))
    if (sel is None or not sel):
        if debug:
            print('No selection! Is there nothing left by join action? *worried*',
            '\n\raborting renaming ...')
        return False
    #deliver the selection
    return sel



#
# Helper for checking for an active object and retrieving it (for single source principle).
#
def isThereActiveObjectThenGet(context):
    #get active object of context
    active_obj = context.active_object
    if (active_obj is None or not active_obj):
        if debug:
            print('No active object -',
            ' trying to make the first object of the selection the active one.')
        #check if selection and get
        sel = isThereSelectionThenGet(context)
        #make first object active (usually it should only be 1 object)
        context.scene.objects.active = sel[0]
    active_obj = context.active_object
    if (active_obj is None or not active_obj):
        if debug:
            print('Still no active object! Aborting renaming ...')
        return False
    #deliver the active object
    return active_obj



#
# Helper for getting basename, i.e. cutting off endings like .001, .002, ...
# @return string:basename aka cleanname
#
def getBaseName(s):
    delimiter = '.'
    obj_basename_parts = s.split(delimiter)
    obj_basename_parts_L = len(obj_basename_parts)
    #if debug:
    #    print('getBaseName: Last part: ', obj_basename_parts[obj_basename_parts_L - 1])
    if (obj_basename_parts_L > 1
    and re.match('[0-9]{3}$', obj_basename_parts[obj_basename_parts_L - 1])):
        #if debug:
        #    print('getBaseName: determining base name')
        # Attention: Last item is left out intentionally (don't remove the '- 1').
        cleanname = obj_basename_parts[0]
        for i in range(1, obj_basename_parts_L - 1):
            cleanname += delimiter + obj_basename_parts[i]
        #done this strange way to avoid unnecessary GUI updates
        #as the sel.name fields in the UI may be unnecessarily updated on change ...
        #if debug:
        #    print('getBaseName: determining *done*, determined basename: ', cleanname)
        return cleanname
    else:
        #if debug:
        #    print('getBaseName: already tidied up *done*, basename: ', s)
        return s
    

    




#------- CLASSES --------------------------------------------------------------#


#
# JoinOrGroupMatchingObjects
#
# Wraps some general attributes and some specific ones
# like the actual content of the regex input field.
#
class OBJECT_OT_Selection2BOM(bpy.types.Operator):
    """Performs the operation (i.e. creating a bill of materials) according to the settings."""
    #=======ATTRIBUTES=========================================================#
    bl_idname = "object.selection2bom"
    bl_label = "Create a Bill of Materials out of selected objects."
    " If no 'Material:<Material>' is given, the blender material is taken"
    " as the desired material. By default Group instances are resolved to"
    " their original group and from there to the therein contained objects"
    " - a group or instance thereof is no individual standalone part by default."
    " Application: Hide objects that shall be excluded from the BoM or select"
    " objects to be included in the BoM explicitely. If no selection is given"
    " then all the not hidden objects and groups are examined."
    bl_context = "objectmode"
    bl_register = True
    bl_undo = True
    #bl_options = {'REGISTER', 'UNDO'}
    
    #=======CONSTRUCTION=======================================================#
    #def __init__(self):
    #=======METHODS============================================================#
    @classmethod
    def poll(cls, context):#it's the same without self (always inserted before)
        # check the context:
        return True  # <-- context does not matter here
        # The following condition no longer is required as auto-detection of mechanical objects is supported.
        # Also the following is not compatible with the possibility to either select objects for the bom
        # or hide objects that shall be exluded.
        #return context.selected_objects is not None && len(context.selected_objects) > 0

    #
    # Command base function (outline).
    #
    def execute(self, context):
        time_start = time.time()
        #processInput(context)
        act(context)
        print("Selection2BoM finished: %.4f sec" % (time.time() - time_start))
        return {'FINISHED'}





#
# GUI Panel
#
# Extends Panel.
#
class VIEW3D_PT_tools_selection2bom(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = 'Selection to Bill of Materials'
    bl_context = 'objectmode'
    bl_options = {'DEFAULT_CLOSED'}
    #DRAW
    def draw(self, context):
        s = context.scene
        in_mode_str = 'Objects'
        #get a string representation of enum button
        if debug:
            print('Mode: ', s.selection2bom_in_mode)
        layout = self.layout
        col = layout.column(align = True)
        col.row().prop(s, 'selection2bom_in_mode', expand = True)
        #splitbutton for enums (radio buttons) ...
        
        row = layout.row(align=True)
        row.prop(s, 'selection2bom_in_precision')

        row = layout.row(align=True)
        row.prop(s, 'selection2bom_in_include_info_line')
        
        row = layout.row(align=True)
        row.prop(s, 'selection2bom_in_include_blueprints')
        
        #col = layout.column(align=True)
        #col.row().prop(s, 'selection2bom_in_scale_factor')#better use the unit settings in scene tab
                
        
        #textfield
        #layout.prop(s, 'joinorgroupbypattern_in_pattern', text = 'Pattern')
        #splitbutton for enums (radio buttons) ...
        #row = layout.row(align = True)
        #only relevant if mode set to join => active (additional option)
        #row.active = (in_mode_str == 'Join')
        #row.prop(s, 'joinorgroupbypattern_in_tidyupnames')
        
        #if (len(s.selected_objects) == 0):
            #col = layout.column(align = True)
            #col.label(text = 'Include hidden objects:')
            #col.row().prop(s, 'joinorgroupbypattern_in_auto_expansion_index_start')
            #col.row().prop(s, 'joinorgroupbypattern_in_auto_expansion_index_end')
            #col.row().prop(s, 'joinorgroupbypattern_in_a_e_digits_total_max')
            #row = layout.row(align = True)
            #row.prop(s, 'selection2bom_in_include_hidden')
            
        
        row = layout.row(align = True)
        label = in_mode_str + " 2 BOM!"
        if (s.selection2bom_in_mode == '0'):
            label = '(Treat assemblies as complete parts.)' + label
        elif (s.selection2bom_in_mode == '1'):
            label = '(Resolve group instances)' + label
        else:#if (s.selection2bom_in_mode == '2'):
            label = '(Both/Hybrid)' + label
            
        row.operator('object.selection2bom', icon='FILE_TICK', text = label)










#------- GENERAL BLENDER SETUP FUNCTIONS --------------------------------------#
#REGISTER
def register():
    bpy.utils.register_module(__name__)
    #bpy.utils.register_class(OBJECT_OT_Selection2BOM)
    #bpy.utils.register_class(VIEW3D_PT_tools_selection2bom)
    
    ## Both independent, for the input-globals see register()!
    #bpy.types.Scene.case_sensitive = True

    ## Difficult to guess unless animation or rendering-related:
    #bpy.types.Scene.skip_non_mechanical_objects = True
    
    # Whether to resolve groups and create BoM entries for contained objects
    # is set in context view 3d panel.
    bpy.types.Scene.after_how_many_create_bom_entry_recursions_to_abort = 100#kind a century :)
    
    #mode
    bpy.types.Scene.selection2bom_in_mode = EnumProperty(
        name = "Mode",
        description = "Select whether to resolve groups & group instances to its"
                " underlaying group's contained objects or if a group"
                " is a standalone part on its own too.",
        items = [
            ("0", "All group instances are atomar, i.e. a complete part on its own.", ""),
            ("1", "Group instances are resolved recursively, only objects are complete parts.", ""),
            ("2", "Hybrid Mode: Group instances both are parts and are resolved into the objects it contains.", "")
        ],
        default='0'
    )
    #tidyupnames
    #bpy.types.Scene.selection2bom_in_include_hidden = BoolProperty(
    #    name = "Include hidden objects?",
    #    description = "Whether to include hidden objects or not.",
    #    default = True
    #)
    #precision
    bpy.types.Scene.selection2bom_in_precision = IntProperty(
        name = "Precision ",
        description = "Precision, i.e. digits after the comma. (e.g. 3 at default metric unit settings results in a resolution of .001m = 1mm.)"
        #,options = {'HIDDEN'}
        ,min = 0
        ,max = 10   #TODO Is it true what I am telling here?
        ,default = 3#mm <- ,001 m = 1 mm => 1 mm resolution we have using 3 digits of floating point precision.
    )
    #scale factor
    bpy.types.Scene.selection2bom_in_scale_factor = IntProperty(
        name = "Scale factor",
        description = "Dimensions in the BoM are multiplied by this scale factor."
        #,options = {'HIDDEN'}
        ,min = 0
        ,max = 1000000
        ,default = 1#keep scale 
    )
    # Shall include extra information (description, URI, ..) line:
    bpy.types.Scene.selection2bom_in_include_info_line = BoolProperty(
        name = "Include datablock label?",
        description = "Whether to include an extra line per BoM entry for e.g. URI, part number, description, ...",
        default = True
    )
    # Shall (generate) and include engineering drawings:
    bpy.types.Scene.selection2bom_in_include_blueprints = BoolProperty(
        name = "Include blueprints?",
        description = "Whether to (generate) and inline-include blueprint for each variant of each bom entry.",
        default = False
    )
    #pass


#UNREGISTER
def unregister():
    bpy.utils.unregister_module(__name__)
    #bpy.utils.unregister_class(OBJECT_OT_Selection2BOM)
    #bpy.utils.unregister_class(VIEW3D_PT_tools_selection2bom)
    #please tidy up
    del bpy.types.Scene.after_how_many_create_bom_entry_recursions_to_abort
    del bpy.types.Scene.selection2bom_in_mode
    #del bpy.types.Scene.selection2bom_in_include_hidden
    del bpy.types.Scene.selection2bom_in_precision
    del bpy.types.Scene.selection2bom_in_include_info_line
    del bpy.types.Scene.selection2bom_in_include_blueprints
    #del bpy.types.Scene.selection2bom_in_scale_factor
    #pass


#------- PROCEDURAL -----------------------------------------------------------#
if __name__ == "__main__":
    #unregister()
    register()


# ########################################################
# Written by macouno for the amazing caliper measurement addon:
# ########################################################


# Add the distance to a string!
def addDistance(distance, length, unit):
    if distance:
        return distance+' '+str(int(length))+unit
    return str(int(length))+unit


	
# FUNCTION FOR MAKING A NEAT METRIC SYSTEM MEASUREMENT STRING
def getMeasureString(distance, unit_settings, precision):

    system = unit_settings.system
    # Whether or not so separate the measurement into multiple units
    separate = unit_settings.use_separate
    # The current measurement (multiplied by scale to get meters as a starting point)
    m = distance * unit_settings.scale_length
    fM = 0
    distance = False
    
    # From chosen to standard international (SI) conversion factors:
    if system == 'METRIC':
        table = [['km', 0.001], ['m', 1000], ['cm', 100], ['mm', 10]]
    elif system == 'IMPERIAL':
        table = [['mi', 0.000621371], ['ft', 5280], ['in', 12], ['thou', 1000]]
    
    # Figure out where to end measuring
    last = len(table)
    if precision < last:
        last = precision
    
    for i, t in enumerate(table):
        step = i
        unit = t[0]
        factor = t[1]
        m = (m - fM) * factor
        fM = math.floor(m)
        
        if fM and not separate:
            rounded = round(m, precision) 
            if precision < 1:
                rounded = int(rounded)
            return str(rounded) + unit
        elif fM:
	    # Make sure the very last measurement is rounded and not floored
            if step > last - 1:
                return addDistance(distance, round(m), unit)
            distance = addDistance(distance, fM, unit)
    
    if not distance:
        return '-' + unit
    
    return distance
	
	
	
