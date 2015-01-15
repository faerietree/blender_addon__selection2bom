#-------------------------------------------------------------------------------
#!/usr/bin/env python
# ========= BLENDER ADD-ON =====================================================

bl_info = {
    "name":         "Selection 2 Bill of Materials",
    "author":       "faerietree (Jan R.I.Balzer-Wein)",
    "version":      (0, 2),
    "blender":      (2, 7, 3),
    "location":     "View3D > Tool Shelf > Misc > Selection 2 BoM",
    "description":  "Either creates a Bill of Materials out of selected objects"
            " (including group instances). Or selects all objects of the current"
            " scene that are not hidden automatically while sorting out rendering-"
            " or animation-related objects like lighting, cameras and armatures."
            " \r\n\nIf no 'Material:<Material>' is given in the object- or groupname"
            " then the blender material is assumed as the desired material."
            " \r\n\nBy default Group instances are resolved to"
            " their original group and those groups to the therein contained objects."
            " => A group or instance thereof is no individual standalone part by default!"
            " \r\n\nLuckily there is an option to consider group instances as complete"
            " independant standalone parts, not resolving the objects but creating"
            " a BoM entry for each group's instances!"
            " \r\n\nA hybrid mode is under development. In this mode the group instances "
            " are grouped and treated as usual standalone part. Each of these assemblies"
            " is resolved too as long as the same kind of assembly not has occurred and"
            " been resolved before. Delta transforms make parts a distinct part."
            " Furthermore group objects inherit the delta transforms!"
            " \r\n\nApplication: Hide objects that shall be excluded from the BoM or select"
            " objects to be included in the BoM explicitely. If no selection is given"
            " then all the not hidden objects and group instances are examined."
            "\r\n\nThe dimensions are calculated from scale times"
            " the object-data dimensions! => Model measurements need to be in real"
            " world size/units or at least have to be scaled to the desired units!",
    "wiki_url": "http://github.com/faerietree/selection2bom",
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
#   where the dimensions are calculated from the scale!
#
# - or the above and additionally resolve groups and sort out rendering-related
#   objects like lighting, cameras and armatures (animation related objects).

# ------- LICENSING ------------------------------------------------------------
# (c) Copyright FarieTree Productions J. R.I.B.-Wein    i@ciry.at
# It's free, as is, open source and property to the World. But without warranty.
# Thus use it, improve it, recreate it and please at least keep the
# origin as in usual citation, i.e. include this Copyright note.
# LICENSE: APACHE
#
# ------------------------------------------------------------------------------



#------- IMPORTS --------------------------------------------------------------#
import bpy
import re
import os

from bpy.props import IntProperty, StringProperty, BoolProperty, EnumProperty




#------- GLOBALS --------------------------------------------------------------#
# Show debug messages in blender console (that is the not python console!)
debug = True

# Both independant, for the input-globals see register()!
case_sensitive = True

# Difficult to guess unless animation or rendering-related:
skip_non_mechanical_objects = True

# Whether to resolve groups and create BoM entries for contained objects
# is set in context view 3d panel.
after_how_many_create_bom_entry_recursions_to_abort = 100#kind a century :)


filelink = None


#------- FUNCTIONS ------------------------------------------------------------#
#COMMAND BASE FUNCTION
def main(context):
    
    #processInput(context)
    act(context)
    return {'FINISHED'}





#ACT
#@return always returns True or False
object_reference_count = {}
def act(context):

    if debug:
        print('engine started ... (acting according to setting)')
    ############
    #preparation - selection
    ############
    
    #----------#
    # At this point a selection must have been made either using
    # 'select by pattern' add-on or by manually selecting the objects/items.
    #----------#
    # Otherwise an effort is undertaken to automatically select mechanical parts.(visible only)
    if (context.selected_objects is None or len(context.selected_objects) == 0):
        #if debug:
        print('No selection! Automatically guessing what to select. (hidden objects are not selected)')
        #ensure nothing is selected
        bpy.ops.object.select_all(action="DESELECT")
        if debug:
            print('deselecting all.')
        #select depending on if it is a mechanical object (TODO)
        for o in context.scene.objects:
            if debug: 
                print('Scene object: ', o)
            if (o.hide):#here we skip hidden objects no matter settings as this way
                # one has the choice to either include object via selecting or
                # or exlude objects by hiding those.
                if debug:
                    print('Auto-selection: Hidden scene object ', o, '.')
                continue
            if (o.type != None):
                if debug:
                    print('Type of scene object: ', o, ' = ', o.type)
                #dupligroup/groupinstance can theoretically be attached to any object, but we only consider those:
                if (not is_object_type_considered(o.type)):
                    continue
                is_longest_object_label_then_store_len(o)  #keep track of longest label length
                is_longest_material_then_store_len(material=o.active_material)
                o.select = True #select object
                context.scene.objects.active = o    #make active
                if debug:
                    print('Selected object: ', o, ' \tactive object: ', context.scene.objects.active)
                    
        #select object instances depending on if it is a mechanical object (TODO)
        for ob in context.scene.object_bases:
            if debug: 
                print('Scene object base: ', ob)
            o = ob.object
            if (o.hide):#here we skip hidden objects no matter settings as this way
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
                #increase the counter for this object as another reference was found?
                if (not (o in object_reference_count)):# || object_reference_count[o] is None):
                    object_reference_count[o] = 0
                object_reference_count[o] = object_reference_count[o] + 1
                #keep track of the longest label's length
                is_longest_object_label_then_store_len(o)
                is_longest_material_then_store_len(material=o.active_material)
                #select the object reference TODO object or the reference which one to select?
                ob.select = True  #select object
                context.scene.objects.active = o    #make active
                if debug:
                    print('Selected object: ', ob, ' \tactive object: ', context.scene.objects.active)



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
    global filelink
    filelink = build_filelink(context)
    
    
    ##########
    # OBJECTS (including group instances as those are attached to objects, see dupligroup 
    #          http://wiki.blender.org/index.php/Doc:2.7/Manual/Modeling/Objects/Duplication/DupliGroup)
    ##########
    result = create_bom_entry_recursively(context, context.selected_objects.copy(), None)#no deepcopy as the objects
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
        write2file(context, bom_entry_count_map)




    return {'CANCELLED'}#TODO The groups (group instances) still show up redundantly (1x <group1>
                                                                                    # 2x <group1>
                                                                                    # 1x <group2>)




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
                
                bom_entry = build_and_store_bom_entry(context, o_g)
                #build_bom_entry() is not enough as we have to keep track of the occurence counts => and store
                append_bom_entry_to_file(context, bom_entry)
        
            
            continue#no further examination of the group's objects
        
        #######
        # RESOLVE GROUP TO OBJECTS
        #######
        #Then in this mode all the objects that make up the group are put into the bill of materials separately.
        for o in g.objects:
            bom_entry = build_and_store_bom_entry(context, o)
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
        print("Keeping track of longest object label's length. Longest length: ", object_longest_label_len)






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





#CREATE BOM ENTRY FROM OBJECT
create_bom_entry_recursion_depth = 0
def create_bom_entry_recursively(context, o_bjects, owning_group_instance_object):
    if debug:
        print('Creating BoM entry recursively ...')
        
    global create_bom_entry_recursion_depth
    create_bom_entry_recursion_depth = create_bom_entry_recursion_depth + 1
    
    if (create_bom_entry_recursion_depth > after_how_many_create_bom_entry_recursions_to_abort):
        if debug:
            print('Failed creating bom entries in time. Recursion limit exceeded: '
                    , create_bom_entry_recursion_depth)
        return {'CANCELLED'}


    
    if debug:
        print('Encountered: ', o_bjects, ' type: ', type(o_bjects))
    
    
    
    #termination condition will be checked here:
    #-------
    # OBJECT?
    #-------
    if ( (o_bjects is object) or (type(o_bjects) is object) or (type(o_bjects) is bpy.types.Object) ):
        
        is_longest_object_label_then_store_len(o_bjects)
        if debug:
            print('Encountered an object: ', o_bjects, ' blender-Type: ', o_bjects.type)
        
        
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
                if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_object)):
                    if debug:
                        print('Failed to write bom entry to file. ', o_bjects, create_bom_entry_recursion_depth)
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
                    print("It's a Group instance! Attached dupli group: ", o_bjects.dupli_group)
                    
                #Resolving groups is not desired?
                if (context.scene.selection2bom_in_mode == '0'):
                    if debug:
                        print('Group shall not be resolved. Is considered a standalone complete part on its own.')
                    #This object is functioning as a group instance container and resembles a standalone mechanical part!
                    #is_to_be_listed_in_bom = True
                    if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_object)): #<-- still attach it to a possible parent group instance.
                        if debug:
                            print('Failed to write bom entry of group instance to file: ', o_bjects, '\t dupli group: ', o_bjects.dupli_group)
                        return {'CANCELLED'}
                    return {'FINISHED'}
                    
                # Hybrid mode? i.e. list in bom and resolve objects too?
                elif (context.scene.selection2bom_in_mode == '2'):
                    if debug:
                        print('Hybrid Mode: Group instances/assemblies are both listed in the bom and resolved.',
                        ' A tree is the desired result, i.e. This assembly exists x times and it is assembled',
                        ' using the following parts.')
                    #is_to_be_listed_in_bom = True
                    is_group_instance_and_needs_to_be_resolved = True
                    if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_object)):
                        if debug:
                            print('Failed to write bom entry of group instance to file: ', o_bjects, '\t dupli group: ', o_bjects.dupli_group)
                # Both mode 1 and 2 need to resolve the group into its objects (if they are not atomar):
                if (o_bjects.name.lower().find('atom:') != -1):
                    return {'FINISHED'}

                # Make an attempt at resolving the group instance into the objects the group contains:
                #Here only group instances are handled! Groups are handled later in the act function. Though that a group exists as one object is not possible and thus they need not to be handled at all. The only chance to encounter a group is via a group instance. Comment will thus be removed in next commit.
                resolve_group_result = o_bjects.dupli_group.objects#resolve_group(group)
                
                #if (context.scene.selection2bom_in_mode == '2'):
                #    build_and_store_bom_entry(context, '------- Parts of assembly `' + o_bjects.dupli_group.name + '`: -------')
                #    #more generic as not every group instance may be a coherent assembly: build_and_store_bom_entry(context, '------- Grouped Parts `' + o_bjects.dupli_group.name + '`: -------')
                if (resolve_group_result is None or (len(resolve_group_result) < 1)):
                    #Group was not resolved successfully!
                    if debug:
                        print('Failed to resolve a group or group was empty. ', str(o_bjects.dupli_group))
                    return {'CANCELLED'}
                    
                #Group resolved into objects!
                if debug:
                    print('Resolved a group. Count of objects in group: ', len(resolve_group_result))
                for obj in resolve_group_result:
                    create_bom_entry_recursively(context, obj, o_bjects)
                    
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
                print('Object type ', o_bjects.type, ' is not considered (e.g. armatures are not considered a mechanical part).')
            return {'CANCELLED'}
            
        
        
    #-------
    # LIST?
    #-------
    elif (o_bjects is list or type(o_bjects) is list):
        print('>> Object is list: ' + str(o_bjects) + ' | type:' + str(type(o_bjects)))
        for o in o_bjects:
            create_bom_entry_recursively(context, o, owning_group_instance_object)
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
#    bom_entry = build_bom_entry(context, o)
#    return write2file(context, bom_entry)
    #ATTENTION: BETTER FIRST CREATE ALL BOM ENTRIES, STORING THEM IN THE UNIQUE ENTRY LIST,
    #INCREMENTING THE EQUAL BOM ENTRY COUNT AND ONLY THEN WRITE THIS TO FILE!
  
  
  
bom_entry_count_map = {}
assembly_bom_entry_count_map = {}
#def init_bom_entry_count_map():
#   pass
def build_and_store_bom_entry(context, o, owning_group_instance_object):#http://docs.python.org/2/tutorial/datastructures.html#dictionaries =>iteritems()
    # Also give parent group instance/assembly to allow to inherit its delta transforms:
    bom_entry = build_bom_entry(context, o, owning_group_instance_object)#http://docs.python.org/3/tutorial/datastructures.html#dictionaries => items() 
    if debug:
        print('Generated BoM entry: ', bom_entry)
    
    #keep track of how many BoM entries of same type have been found.
    if (not (bom_entry in bom_entry_count_map)):
        if debug:
            print('From now on keeping track of bom_entry count of ', bom_entry)
        bom_entry_count_map[bom_entry] = 0
        
    bom_entry_count_map[bom_entry] = bom_entry_count_map[bom_entry] + 1
    if debug:
        print('-> new part count: ', bom_entry_count_map[bom_entry], 'x ', bom_entry)
        
    # Have to add assembly entry?
    if (owning_group_instance_object is not None):
        # Important Note: The last item of the list could be spliced out! It's not done for performance. It's tested if for equality and skipped instead - in build_bom_entry().
        assembly_bom_entry = build_bom_entry(context, owning_group_instance_object, None) #TODO store owning_group_instance_objects and iterate bottom up.
        # Keep track of how many BoM entries of the same type belong to this unique assembly:
        if (not (assembly_bom_entry in assembly_bom_entry_count_map)):
            if debug:
                print('From now on keeping track of assembly: ', assembly_bom_entry)
            assembly_bom_entry_count_map[assembly_bom_entry] = {}
            
        if (not (bom_entry in assembly_bom_entry_count_map)):
            if debug:
                print('Assembly: From now on keeping track of bom_entry count of ', bom_entry)
            assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] = 0
    
        assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] = assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] + 1
        if debug:
            print('Assembly:', assembly_bom_entry, ' -> new part count: ', assembly_bom_entry_count_map[assembly_bom_entry][bom_entry], 'x ', bom_entry)
        
    return bom_entry
    
    
    
 
#    
#g: bpy.types.Group not a group instance, i.e. no object with dupli group bpy.types.Group attached
def build_and_store_bom_entry_out_of_group(context, g):
    if debug:
        print('Encountered a group that should have been added to the BoM: ', g)
    #return build_and_store_bom_entry_out_of_group(context, g)
    return '\r\nBuilding bom entry out of group not supported yet. Possibly solve it analoguously to group instance dimension resolving.'

    

def build_bom_entry(context, o, owning_group_instance_object):
    #build BoM entry: using http://www.blender.org/documentation/blender_python_api_2_69_release/bpy.types.Object.html
    entry = getBaseName(o.name)
    
    index = -1
    material = '-'
    if (o.active_material is None):
        if debug:
            print('Object ', o, ' has no active material.')
        if (not (o.dupli_group is None)):
            print('It\'s a dupli group attached to this object. => This is a group instance. => Resolving material from its objects.')
            found_material_within_group_objects = False
            for group_object in o.dupli_group.objects:
                if (not (group_object.active_material is None)):
                    found_material_within_group_objects = True
                    material = getBaseName(group_object.active_material.name)
                    break#leave the loop as we have achieved our goal
            if (debug and not found_material_within_group_objects):
                print('Found no next best material within the attached group object members: ', o.dupli_group.objects)
    else:
        material = getBaseName(o.active_material.name)    #default value
        
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
                
    #keep track of the longest material label
    is_longest_material_then_store_len(material_label=material)
    
    #dimensions
    context.scene.objects.active = o
    result = {'CANCELLED'}
    operations_to_undo_count = 0
    #if (not (context.active_object is None)):
    #    #because multi-user mesh does not allow applying modifiers
    #    if (bpy.ops.object.make_single_user(object=True, obdata=True)):#, material=True, texture=True, animation=True)):
    #        operations_to_undo_count = operations_to_undo_count + 1
    #        for m in o.modifiers:
    #            result = bpy.ops.object.modifier_apply(modifier=m.name)
    #            #bpy.ops.object.modifier_apply()#'DATA', '')#applies on the active object
    #            if (result):
    #                operations_to_undo_count = operations_to_undo_count + 1
    
    
    #######
    # DIMENSIONS
    #######
    #TODO don't take the absolute bounding_box dimensions -instead calculate form object.bounding_box (list of 24 space coordinates)
    #As a group instance is a dupli group holding empty object, it may have dimensions or (delta) transform other than zero. So deal with it.
    #undo_count = 0 #now working with a copy of the initially selected_objects (no longer a live copy/reference)
    x = o.dimensions[0] # As it's in object context, the scale is taken into account in the bounding box already.
    y = o.dimensions[1]
    z = o.dimensions[2]
    # If provided inherit parent group instance's transforms:
    if (owning_group_instance_object is not None): # TODO iterate here and check for o and owning_o equality and skip if equal (see performance hack, it's done to avoid removing element from the list which is live and still needed later).
        x *= owning_group_instance_object.scale[0]
        y *= owning_group_instance_object.scale[1]
        z *= owning_group_instance_object.scale[2]
        x *= owning_group_instance_object.delta_scale[0]
        y *= owning_group_instance_object.delta_scale[1]
        z *= owning_group_instance_object.delta_scale[2]
        
    if (not (o.dupli_group is None)):
        if debug:
            print('Creating temporary selection.')#To be undone or unexpected results will
            # occur as the loop uses a live copy of selection. <-- No longer valid!
            # Now using a copy of the dict for the recursion create_bom_entry_recursively.
        
        #ensure nothing is selected
        if (not bpy.ops.object.select_all(action="DESELECT")):
            print('There seems to be already no selection - that may be interesting, but as we work with a copy it should not matter. Of importance is that now nothing is selected anymore.')
        #undo_count = undo_count + 1
        o.select = True
        #undo_count = undo_count + 1
        
        #BELOW THIS LINE NOTHING HAS TO BE UNDONE! AS THIS DUPLICATED OBJECT
        #(GROUP INSTANCE) WILL SIMPLY BE DELETED AFTERWARDS.
        if (not bpy.ops.object.duplicate()):#non-linked duplication of selected objects
            print('duplicate failed')
            
        if (len(context.selected_objects) > 1):
           print('Only one object (the group instance) should have been selected.\r\nSelection: ', context.selected_objects, '. Thus dimension will only reflect those of the dupli group objects of the first selected group instance object.')
        context.scene.objects.active = context.selected_objects[0]
        if debug:
            print('active object after duplication of group instance: ', context.active_object, ' or :', context.scene.objects.active)
     
        # That this condition is true is very UNLIKELY because we just copied the group instance and checked before that dupli_group in not None!  
        if (context.scene.objects.active.dupli_group is None):
            print('The active object is no group instance after the duplication for determining dimension!? Looking for a group instance in selection now ...')
            is_group_instance_found = False
            #This loop is a not very likely as we have or rather should only one object in the selection!
            for selected_o in context.selected_objects:
                if (not(selected_o.dupli_group is None)):
                   context.scene.objects.active = selected_o
                   is_group_instance_found = True
                   print('found ', selected_o)
                   break
                else:
                   selected_o.select = False#TODO is that a good idea or even required?
            if (not is_group_instance_found):
                print('No group instance found in temporarey selection. Aborting ...')

        
        #the active object (group instance) should be the only selected one:
        bpy.ops.object.duplicates_make_real(use_base_parent=True)#false because we don't set up
                #the empty group instance as parent of the now copied and no longer referenced group objects!
                #The dupli group attached to this object
                #is copied here as real value object copies (not references).
        
        #new group instance hopefully is the active object now:
        group_objects_count = 0
        for group_object in context.scene.objects.active.children:#dupli_group.objects:
            if (group_object.type == 'EMPTY' or group_object.type == 'Armature'):
                #and is_object_type_considered(group_object_type)):
                print ('Warning: Group object\'s type is EMPTY or ARMATURE. Skipping it as these have no dimensions anyway.')
                continue
            if (not group_object.type == 'MESH'):
                group_object.select = False #required because of joining only allows mesh or curve only - no mix!
            group_object.select = True
            ++group_objects_count
        #Note:
        # The real objects that now reside where the group instance was before
        # should already be selected after duplicates_make_real.
        
        
        context.scene.objects.active = context.selected_objects[group_objects_count - 1]
        if debug:
            print(context.selected_objects, '\r\nactive_object: ', context.active_object)
        #Attention: Poll fails because a context of joining into an empty (as this is the active object) is not valid!
        if (not bpy.ops.object.join()):
            print('Joining the temporary selection (dupli group made real) failed.')
            #break
            
        
        x = context.active_object.dimensions[0]
        y = context.active_object.dimensions[1]
        z = context.active_object.dimensions[2]
        
        #now no longer required (copy instead of selected_object reference for recursion used now)
        #while --undo_count > 0:
        #    bpy.ops.ed.undo()
        bpy.ops.object.delete(use_global=False)#The duplicate should reside in this context's scene only!
        

    #measure
    unit = 'm'
    if (context.scene.unit_settings.system == 'IMPERIAL'):
        unit = 'ft'
    #determine units using the unit scale of the scene's unit/world settings
    dimensions = [
        str(round(x * context.scene.unit_settings.scale_length, context.scene.selection2bom_in_precision)) + unit,
        str(round(y * context.scene.unit_settings.scale_length, context.scene.selection2bom_in_precision)) + unit,
        str(round(z * context.scene.unit_settings.scale_length, context.scene.selection2bom_in_precision)) + unit
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
    
    whitespace_count = object_longest_label_len - len(entry)
    material_whitespace_count = material_longest_label_len - len(material)
    if debug:
        print('object whitespace count: ', whitespace_count, '\t material whitespace count: ', material_whitespace_count)
    bom_entry = '\t \t' + entry + getWhiteSpace(whitespace_count) + '\t \tMaterial: ' + material + getWhiteSpace(material_whitespace_count) + '\t \t[x:' + dimensions[0] + ',y:' + dimensions[1] + ',z:' + dimensions[2] + ']'
            #TODO take modifiers array, skin
            # and solidify into account (by e.g. applying all modifiers, examining and storing the dimensions and going
            #back in history to pre applying the modifiers!
            
            #NOT RELEVANT: + '\t \t[object is in group: ' o.users_group ', in Scenes: ' o.users_scene ']'
            
    return bom_entry






 

#
# White space for filling up to a certain length.
#
def getWhiteSpace(count):
    whitespace = ''
    for i in range(0, count - 1):
        whitespace = whitespace + ' '
    return whitespace





#
# All found bom entries are written to a file.
#
def write2file(context, bom_entry_count_map):#<-- argument is a dictionary (key value pairs)!
    if debug:
        print('Writing bill of materials to file ...')
        
    global filelink
    if (filelink is None):
        filelink = build_filelink(context)
    if debug:
        print('Target filelink: ', filelink)
        
    #write to file
    result = False
    with open(filelink, 'w') as f:#for closing filestream automatically
        #f.read()
        #f.readhline()
        bom = ''
        for entry, entry_count in bom_entry_count_map.items(): 
            bom = bom + '\r\n' + str(entry_count) + 'x ' + entry
            #bom = bom '\r\n'
            
        result = f.write(bom)
        if (result):
            print('Bill of materials created: ', filelink)
        else :
            print('Bill of materials: creation failed! ', filelink)
    return result
        
    

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



def build_filelink(context):
    if debug:
        print('building filelink ...')

    #build filelink
    root = bpy.path.abspath('//') 
    #root = './'#using relative paths -> to home directory
    #root = os.getcwd()#<-- current working directory, so where the blender was launched from.
    print('Root: ' + root)
    #root = dirname(pathname(__FILE__))#http://stackoverflow.com/questions/5137497/find-current-directory-and-files-directory
    filename = 'BoM-'#TODO Determine this blender file name!
    fileending = '.txt'
    
    #objectname = getBaseName(context.selected_objects[0].name)
    objectname = context.scene.objects.active #context.active_object    
    objectname = context.scene.name
    if (not objectname or objectname is None):
        objectname = 'no-or-buggy-active-object'
    
    filename = filename + objectname
    filelink = root + '/' + filename + fileending
    
    #don't overwrite existing boms because for several selections individual boms
    # could be desired.
    number = 0
    while (os.path.isfile(filelink)):#alternatively: try: with (open(filelink)): ... except IOError: print('file not found') 
        number = number + 1              #http://stackoverflow.com/questions/82831/how-do-i-check-if-a-file-exists-using-python
        filename_ = filename + str(number)
        filelink = filename_ + fileending

    #A non-existant filelink for the bill of materials was found.
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





#HELPER - ISTHERESELECTION
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





#HELPER - ISTHEREACTIVEOBJECT
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





#HELPER - GETBASENAME
#@return string:basename aka cleanname
def getBaseName(s):
    obj_basename_parts = s.split('.')
    obj_basename_parts_L = len(obj_basename_parts)
    if debug:
        print('getBaseName: Last part: ', obj_basename_parts[obj_basename_parts_L - 1])
    if (obj_basename_parts_L > 1
    and re.match('[0-9]{3}$', obj_basename_parts[obj_basename_parts_L - 1])):
        if debug:
            print('getBaseName: determining base name')
        #attention: last item is left intentionally
        cleanname = ''
        for i in range(0, obj_basename_parts_L - 1):
            cleanname += obj_basename_parts[i]
        #done this strange way to avoid unnecessary GUI updates
        #as the sel.name fields in the UI may be unnecessarily updated on change ...
        if debug:
            print('getBaseName: determining *done*, determined basename: ', cleanname)
        return cleanname
    else:
        if debug:
            print('getBaseName: already tidied up *done*, basename: ', s)
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
        #check the context
        #context does not matter here
        return True
        #The following condition no longer is required as auto-detection of mechanical objects is supported.
        #Also the following is not compatible with the possibility to either select objects for the bom
        #or hide objects that shall be exluded.
        #return context.selected_objects is not None && len(context.selected_objects) > 0

    def execute(self, context):
        main(context)
        return {'FINISHED'}





#
# GUI Panel
#
# Extends Panel.
#
class VIEW3D_PT_tools_selection2bom(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = 'Selection to BoM'
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
    bpy.types.Scene.selection2bom_in_include_hidden = BoolProperty(
        name = "Include hidden objects?",
        description = "Whether to include hidden objects or not.",
        default = True
    )
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
    #pass


#UNREGISTER
def unregister():
    bpy.utils.unregister_module(__name__)
    #bpy.utils.unregister_class(OBJECT_OT_Selection2BOM)
    #bpy.utils.unregister_class(VIEW3D_PT_tools_selection2bom)
    #please tidy up
    del bpy.types.Scene.selection2bom_in_mode
    del bpy.types.Scene.selection2bom_in_include_hidden
    del bpy.types.Scene.selection2bom_in_precision
    del bpy.types.Scene.selection2bom_in_scale_factor
    #pass


#------- PROCEDURAL -----------------------------------------------------------#
if __name__ == "__main__":
    #unregister()
    register()
    # test call
    #bpy.ops.object.join_or_group_by_pattern()
