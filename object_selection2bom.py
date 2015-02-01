#-------------------------------------------------------------------------------
#!/usr/bin/env python
# ========= BLENDER ADD-ON =====================================================

bl_info = {
    "name":         "Selection 2 Bill of Materials",
    "author":       "faerietree (Jan R.I.Balzer-Wein)",
    "version":      (0, 8),
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



def initaddon(context):
    global bom_entry_count_map
    global assembly_count_map
    global assembly_bom_entry_count_map
    bom_entry_count_map = {}
    assembly_count_map = {}
    assembly_bom_entry_count_map = {}

#ACT
#@return always returns True or False
object_reference_count = {}
def act(context):
    global bom_entry_count_map
    global assembly_count_map
    global assembly_bom_entry_count_map
    
    initaddon(context)

    if debug:
        print('engine started ... (acting according to setting)')
    ############
    #preparation - selection
    ############
    scene_layers_to_restore = list(context.scene.layers)
    if debug:
        print('Should be true: ', id(scene_layers_to_restore), ' != ', id(context.scene.layers))
    
    #----------#
    # At this point a selection must have been made either using
    # 'select by pattern' add-on or by manually selecting the objects/items.
    #----------#
    # Otherwise an effort is undertaken to automatically select mechanical parts.(visible only)
    if (context.selected_objects is None or len(context.selected_objects) == 0):
        #if debug:
        print('No selection! Automatically guessing what to select. (hidden objects are not selected)')
        # Ensure nothing is selected
        if debug:
            print('deselecting all.')
        deselect_all(context)
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
                    
    else:
       # Ensure that all layers are visible to prevent resolved objects (from group instances) not being listed in the BoM.
       context.scene.layers = (True, True, True, True, True,  True, True, True, True, True,  True, True, True, True, True, True,  True, True, True, True)

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
    result = create_bom_entry_recursively(context, context.selected_objects.copy(), [])#no deepcopy as the objects
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
        write2file(context, bom_entry_count_map, assembly_count_map, assembly_bom_entry_count_map)

    context.scene.layers = scene_layers_to_restore


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










#CREATE BOM ENTRY FROM OBJECT
def create_bom_entry_recursively(context, o_bjects, owning_group_instance_objects, recursion_depth=0):
    if debug:
        print(str(recursion_depth) + ' Creating BoM entry recursively ...')
        
    if (recursion_depth > after_how_many_create_bom_entry_recursions_to_abort):
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
    if ( (o_bjects is object) or (type(o_bjects) is object) or (type(o_bjects) is bpy.types.Object) ):
        
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
                if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_objects)):
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
                    if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_objects)): #<-- still attach it to a possible parent group instance.
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
                    if (not build_and_store_bom_entry(context, o_bjects, owning_group_instance_objects)):
                        if debug:
                            print('Failed to write bom entry of group instance to file: ', o_bjects, '\t dupli group: ', o_bjects.dupli_group)
                # Both mode 1 and 2 need to resolve the group into its objects (if they are not atomar):
                if (is_atomar(o_bjects)):
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
                owning_group_instance_objects.append(o_bjects) 
                for obj in resolve_group_result:
                    create_bom_entry_recursively(context, obj, owning_group_instance_objects, recursion_depth=(recursion_depth + 1))
                
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
            create_bom_entry_recursively(context, o, owning_group_instance_objects, recursion_depth=(recursion_depth + 1))
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

def is_object_atomar(o):
    return (re.search('^' + 'atom' + '[-_: ]+', o.name.lower()) != None)
    
def is_object_optional(o):
    return (re.search('^' + 'optional' + '[-_: ]+', o.name.lower()) != None)
    


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
assembly_count_map = {}
assembly_bom_entry_count_map = {}
#def init_bom_entry_count_map():
#   pass
def build_and_store_bom_entry(context, o, owning_group_instance_objects):#http://docs.python.org/2/tutorial/datastructures.html#dictionaries =>iteritems()
    global bom_entry_count_map
    global assembly_count_map
    global assembly_bom_entry_count_map
    
    # Also give parent group instance/assembly to allow to inherit its delta transforms:
    bom_entry = build_bom_entry(context, o, owning_group_instance_objects)#http://docs.python.org/3/tutorial/datastructures.html#dictionaries => items() 
    if debug:
        print('Generated BoM entry: ', bom_entry)
    
    #keep track of how many BoM entries of same type have been found.
    count_map = bom_entry_count_map
    # In hybrid mode?
    if (context.scene.selection2bom_in_mode == '2'):
        # In hybrid mode the assemblies are listed separately.
        # Should not occur in the global parts lists if they are not atomar.
        if debug:
            print('==========> dupli_group: ', o.dupli_group)
        if (not (o.dupli_group is None) and len(o.dupli_group.objects) > 0):
            if debug:
                print('==========> is atomar: ', is_atomar(o))
            if (not is_atomar(o)):
                if debug:
                    print('Assembly found: ', o, '\r\n=> Putting into assembly_count_map.')
                count_map = assembly_count_map
        
    if (not (bom_entry in count_map)):
        if debug:
            print('From now on keeping track of bom_entry count of ', bom_entry)
        count_map[bom_entry] = 0
        
    count_map[bom_entry] = count_map[bom_entry] + 1
    if debug:
        print('-> new part count: ', count_map[bom_entry], 'x ', bom_entry)
    # To know how much compensating whitespace to insert later:
    is_longest_entry_count_then_store_len(count_map[bom_entry])  
    
    # Have to add assembly entry?
    owning_group_instance_objects_length = len(owning_group_instance_objects)
    if (owning_group_instance_objects_length > 0):
    #for i in range(owning_group_instance_objects_length - 1, -1):
        # Important Note: The last item of the list could be spliced out! It's not done for performance. It's tested if for equality and skipped instead - in build_bom_entry().
        parent_group_instance = None
        if (owning_group_instance_objects_length > 0):
            parent_group_instance = owning_group_instance_objects[owning_group_instance_objects_length - 1]
        if debug:
            print('Assembly: Building bom entry ...')
        assembly_bom_entry = build_bom_entry(context, parent_group_instance, owning_group_instance_objects) #TODO store owning_group_instance_objects and iterate bottom up.
        # Keep track of how many BoM entries of the same type belong to this unique assembly:
        if (not (assembly_bom_entry in assembly_bom_entry_count_map)):
            if debug:
                print('Assembly: From now on keeping track of assembly: ', assembly_bom_entry)
            assembly_bom_entry_count_map[assembly_bom_entry] = {}
            
        if (not (bom_entry in assembly_bom_entry_count_map[assembly_bom_entry])):
            if debug:
                print('Assembly: From now on keeping track of bom_entry count of ', bom_entry)
            assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] = 0
    
        assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] = assembly_bom_entry_count_map[assembly_bom_entry][bom_entry] + 1
        if debug:
            print('Assembly:', assembly_bom_entry, ' -> new part count: ', assembly_bom_entry_count_map[assembly_bom_entry][bom_entry], 'x ', bom_entry)
    
    print('----*done*,constructed bom entries.')
    return bom_entry
    
    
    
 
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


def build_bom_entry(context, o, owning_group_instance_objects):
    if debug:
        print('build_bom_entry: o:', o, ' owning_group_instance_objects:', owning_group_instance_objects)
    #build BoM entry: using http://www.blender.org/documentation/blender_python_api_2_69_release/bpy.types.Object.html
    entry = getBaseName(o.name)
    
    index = -1
    material = '-'
    if (o.active_material is None):
        if debug:
            print('Object ', o, ' has no active material.')
        if (not (o.dupli_group is None)):
            if debug:
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
    
    # Remove indicators:
    atomar_indicator = 'atom'
    index = entry.find('' + atomar_indicator)
    if (index != -1):
        pattern = '^' + atomar_indicator + '[-_: ]+'
        entry = re.sub(pattern, '', entry)
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
        pattern = indicator + '[-_: ]+'
        entry = re.sub(pattern, '', entry)
    

    #keep track of the longest material label
    is_longest_material_then_store_len(material_label=material)
    
    #dimensions
    context.scene.objects.active = o
    result = {'CANCELLED'}
    #operations_to_undo_count = 0
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
    # If provided inherit parent group instances' transforms:
    # If o owning_o equality and skip if equal (see performance hack, it's done to avoid removing element from the list which is live and still needed later).
        
    if (not (o.dupli_group is None) and len(o.dupli_group.objects) > 0):
        if debug:
            print('Creating temporary selection. o: ', o, ' dupli_group: ', o.dupli_group)#To be undone or unexpected results will
            # occur as the loop uses a live copy of selection. <-- No longer valid!
            # Now using a copy of the dict for the recursion create_bom_entry_recursively.
        
        objects_to_be_deleted = [] # Contains all duplicated/temporary objects. 
        objects_to_be_joined = [] # A subset of the above because only MESH objects are joined.
        
        resolve_all_joinable_objects_recursively(context, o, objects_to_be_joined, objects_to_be_deleted)
        
        # Ensure nothing is selected:
        deselect_all(context)
        
        # TODO As resolving group instances recursively is costly, it would be nice to use more of the info gained. 
        # TODO When to apply modifiers?
        
        objects_to_be_joined_length = len(objects_to_be_joined)
        if objects_to_be_joined_length > 0:
            for objects_to_be_joined_index in range(0, objects_to_be_joined_length):
                objects_to_be_joined[objects_to_be_joined_index].select = True
        
            # Arbitrarily choose the last object as target:
            context.scene.objects.active = objects_to_be_joined[objects_to_be_joined_length - 1]
            if debug:
                print(context.selected_objects, '\r\nactive_object: ', context.active_object)
                print('joining ...')
            # Attention: Poll may fail because a context of joining into an empty is not valid!
            if (not bpy.ops.object.join()):
                print('Joining the temporary selection (all group instances within this group instance duplicated, made real and its dupli groups\' objects recursively treated the same too) failed. Check for unjoinable object types.')
                #break
            if (not context.scene.objects.active):
                print('WARNING: Active object not set after join operation.')
            else:
                context.scene.objects.active.select = True
        else:
            # TODO Use the dimension of the greatest object within its dupligroup (this includes CURVE objects). Only adopt if greater than the currenty evaluated object's dimensions.
            o.select = True # If the above functionality isn't, then this may be simplified. This is obsolete as it's the default dimension anyway.
            context.scene.objects.active = o
        print('Adopting total dimensions of the complete assembly (joined): ', context.scene.objects.active)    
        # Inherit the dimensions. 
        x = context.active_object.dimensions[0]
        y = context.active_object.dimensions[1]
        z = context.active_object.dimensions[2]
        
        ##Undo now no longer required (copy instead of selected_object reference for recursion used now)
        #while --undo_count > 0:
        #    bpy.ops.ed.undo()
        if (context.active_object == o):
            o.select = False
        if len(context.selected_objects) > 0:
            if debug:
                print(context.selected_objects, '\r\nactive_object: ', context.active_object)
                print('deleting ...')
            bpy.ops.object.delete()
        else:
            print('WARNING: No objects selected but it should. Might have found nothing to join ...')
        # Ensure nothing is selected:
        if (len(context.selected_objects) > 0):
            deselect_all(context)
        # Select all objects that still have to be deleted (all but the joined ones):    
        objects_to_be_deleted_length = len(objects_to_be_deleted)
        if (objects_to_be_deleted_length > 0):
            for objects_to_be_deleted_index in range(0, objects_to_be_deleted_length):
                if objects_to_be_deleted[objects_to_be_deleted_index] in objects_to_be_joined:
                    print('Skipping object to be deleted because it may (rather should) have been joined: ', objects_to_be_deleted[objects_to_be_deleted_index])
                    continue
                objects_to_be_deleted[objects_to_be_deleted_index].select = True
            if debug:
                print(context.selected_objects, '\r\nactive_object: ', context.active_object)
                print('deleting ...')
            bpy.ops.object.delete()
        #TODO take modifiers array, skin
        # and solidify into account (by e.g. applying all modifiers, examining and storing the dimensions and going
        #back in history to pre applying the modifiers!
        
        
    # Apply inherited delta transforms:    
    owning_group_instance_objects_length = len(owning_group_instance_objects)
    owning_group_instance_objects_index = owning_group_instance_objects_length - 1
    is_optional = False
    while owning_group_instance_objects_index > -1:
        #print('index: ', owning_group_instance_objects_index, ' of length ', owning_group_instance_objects_length)
        owning_group_instance_object = owning_group_instance_objects[owning_group_instance_objects_index]
        # The object o itself might reside at the last position in the list, for performance reasons it was not removed. So skip it:
        if (owning_group_instance_object != o):
            x *= owning_group_instance_object.scale[0]
            y *= owning_group_instance_object.scale[1]
            z *= owning_group_instance_object.scale[2]
            x *= owning_group_instance_object.delta_scale[0]
            y *= owning_group_instance_object.delta_scale[1]
            z *= owning_group_instance_object.delta_scale[2]
           
        if (is_object_optional(owning_group_instance_object)):
            is_optional = True
          
        owning_group_instance_objects_index -= 1


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
    bom_entry = entry + '___' + material + '___[' + dimensions[0] + ' x ' + dimensions[1] + ' x ' + dimensions[2] + ']___'
    if (is_optional):
        bom_entry = bom_entry + '1'
    #else:
    #    bom_entry = bom_entry + '0'
        
    #bom_entry = '\t' + entry + getWhiteSpace(whitespace_count) + '\tMaterial: ' + material + getWhiteSpace(material_whitespace_count) + '\t[' + dimensions[0] + ' x ' + dimensions[1] + ' x ' + dimensions[2] + ']'
            
    #NOT RELEVANT: + '\t \t[object is in group: ' o.users_group ', in Scenes: ' o.users_scene ']'
            
    return bom_entry



        
def resolve_all_joinable_objects_recursively(context, o, objects_to_be_joined, objects_to_be_deleted, is_already_duplicate=False, recursion_depth=0):
    #print(str(recursion_depth) + 'resolve_all_joinable_objects_recursively: o: ',o, ' to_be_joined: ', objects_to_be_joined, ' objects_to_be_deleted: ', objects_to_be_deleted)
    if (recursion_depth > after_how_many_create_bom_entry_recursions_to_abort):
        print(str(recursion_depth) + ' Reached recursion depth limit: ', after_how_many_create_bom_entry_recursions_to_abort, ' current recursion depth: ', recursion_depth)
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
   
   
    # If the objects are duplicated, then they still are in the same groups as the original object. This means the dupli_group suddenly has more members, which leads to endless recursion. Thus remove the duplicates from all groups:
    if debug:
        print('Removing selected objects from all groups. ', context.selected_objects)
    #for selected_duplicate in context.selected_objects:
    #    for d_group in selected_duplicate.users_group:
    #        bpy.ops.group.objects_remove(group=d_group)
    bpy.ops.group.objects_remove_all()
    
    # As this is a duplicate, it needs to be removed later on:
    # Required because of joining only allows mesh or curve only - no mix!
    if (context.scene.objects.active.type == 'MESH'):
        objects_to_be_joined.append(context.scene.objects.active)
    else:  
        objects_to_be_deleted.append(context.scene.objects.active) # It's safer here as joining into an active object keeps up the active object of course. Thus the object should be deleted but it is not as it has been marked for join. Thus better not even mark for deletion.

    # Further decomposition possible? 
    if (not (context.scene.objects.active.dupli_group is None)):
        # Store a reference because it's not certain that an operator not changes the active object.
        group_instance_object = context.scene.objects.active
        if debug:
            print('Making real ...') 
        #the active object (group instance) should be the only selected one:
        bpy.ops.object.duplicates_make_real(use_base_parent=True)#false because we don't set up
                #the empty group instance as parent of the now copied and no longer referenced group objects!
                #The dupli group attached to this object
                #is copied here as real value object copies (not references). Though as it's apparently linked,
                #making single user is required:
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
            # If EMPTY is a considered type, then the empty corresponding to the current object (that also reside after duplicates_make_real) must be skipped:
            if (group_object == group_instance_object):
                if debug:
                    print('>> Skipping group object because it\'s the group instance object itself.')
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
    if (count < 0):
        return ''
    count = int(round(count, 0))
    whitespace = ''
    for i in range(0, count): # range() is exclusive at the upper bound.
        whitespace = whitespace + ' '
    return whitespace

#
#
#
def processEntry(entry):
        
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
    return '\t' + pre + label + getWhiteSpace(whitespace_count) + '\tMaterial: ' + material + getWhiteSpace(material_whitespace_count) + '\t' + dimensions + post


#
# All found bom entries are written to a file.
#
PREPEND_IF_OPTIONAL = '('
APPEND_IF_OPTIONAL = ')'
def write2file(context, bom_entry_count_map, assembly_count_map, assembly_bom_entry_count_map):#<-- argument is a dictionary (key value pairs)!
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
        
        bom = getWhiteSpace(entry_count_highest_digit_count) + '#\tLabel' + getWhiteSpace(object_longest_label_len - 5) + '\t\tMaterial ' + getWhiteSpace(material_longest_label_len - 8) + '\t\t\tDimensions'
        bom = bom + '\r\n'
        bom = bom + getWhiteSpace(entry_count_highest_digit_count) + '-\t-----' + getWhiteSpace(object_longest_label_len - 5) + '\t\t---------' + getWhiteSpace(material_longest_label_len - 8) + '\t\t\t----------'
        bom = bom + '\r\n'
        # Total part (counts):
        for entry, entry_count in bom_entry_count_map.items(): 
            pre = ''
            if (entry.split('___')[3] != ''):
                pre = PREPEND_IF_OPTIONAL
            digit_count = len(str(entry_count) + pre)
            whitespace_count = entry_count_highest_digit_count + len(PREPEND_IF_OPTIONAL) - digit_count
            bom = bom + '\r\n' + pre + getWhiteSpace(whitespace_count * .9) +  str(entry_count) + 'x ' + processEntry(entry)
            #bom = bom '\r\n'
            
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
                bom = bom + '\r\n' + pre + getWhiteSpace(whitespace_count) + str(assembly_count) + 'x ' + processEntry(assembly) + ':'
                
                bom = bom + '\r\n-------'
                for entry, entry_count in entry_count_map.items(): 
                    pre = ''
                    if (entry.split('___')[3] != ''):
                        pre = PREPEND_IF_OPTIONAL 
                    count_string = str(int(round(entry_count/assembly_count, 0)))# + '(' + str(entry_count) + ')')
                    digit_count = len(count_string + pre)
                    whitespace_count = entry_count_highest_digit_count + len(PREPEND_IF_OPTIONAL) - digit_count
                    bom = bom + '\r\n' + pre + getWhiteSpace(whitespace_count) + count_string + 'x ' + processEntry(entry)
                    #bom = bom '\r\n'
                    
                bom = bom + '\r\n--------------\r\n\r\n'
                  
            
            
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
        filelink = root + '/' + filename_ + fileending

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
    #if debug:
    #    print('getBaseName: Last part: ', obj_basename_parts[obj_basename_parts_L - 1])
    if (obj_basename_parts_L > 1
    and re.match('[0-9]{3}$', obj_basename_parts[obj_basename_parts_L - 1])):
    #    if debug:
    #        print('getBaseName: determining base name')
        # Attention: Last item is left out intentionally (don't remove the '- 1').
        cleanname = ''
        for i in range(0, obj_basename_parts_L - 1):
            cleanname += obj_basename_parts[i]
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
