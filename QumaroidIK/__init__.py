bl_info = {
    'name': 'Qumaroid IK Plugin',
    'category': '3D View',
    'author': 'Akiba Akira',
    'description': 'Qumarion IK Helper',
    'version': (0, 19, 0),  
    'blender': (2, 80, 0),
    'warning': '',
}

from logging import root
from unittest import result
import bpy, math, re

class QumaPrepareHairIK(bpy.types.Operator):
    bl_label = "Hair IK"
    bl_idname = "object.quma_ik_prepare_hair"
    bl_description = "Active IK on Hair"

    def execute(self, context):
        if context.scene.qumaroidArmatureObject:
            context.scene.qumaroidIsIKPosing = True
            QumaHairIK.CreateHairIKChain(context.scene.qumaroidArmatureObject)
        return {'FINISHED'}

class QumaApplyHairIK(bpy.types.Operator):
    bl_label = "Apply Hair IK"
    bl_idname = "object.quma_ik_apply_hair"
    bl_description = "Apply IK on Hair"

    def execute(self, context):
        if context.scene.qumaroidArmatureObject:
            context.scene.qumaroidIsIKPosing = True
            QumaHairIK.ApplyIK(context.scene.qumaroidArmatureObject)
        return {'FINISHED'}

class QumaIKPanel(bpy.types.Panel):

    bl_label = "Qumarion IK Helper"
    bl_idname = "SCENE_PT_qumarion_IK_panel"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Item"

    def draw(self, context):

        layout = self.layout
        scene = context.scene

        # if scene.qumaroidArmatureObject is not None:

        row = layout.row()
        row.operator("object.quma_ik_prepare_hair")
        
        row = layout.row()
        row.operator("object.quma_ik_apply_hair")

def register():
    bpy.utils.register_class(QumaIKPanel)

    bpy.utils.register_class(QumaPrepareHairIK)
    bpy.utils.register_class(QumaApplyHairIK)

    bpy.types.Scene.qumaroidIsIKPosing = bpy.props.BoolProperty()
    
def unregister():
    bpy.utils.unregister_class(QumaIKPanel)  
    
    bpy.utils.unregister_class(QumaPrepareHairIK)
    bpy.utils.unregister_class(QumaApplyHairIK)

    del bpy.types.Scene.qumaroidIsIKPosing

class QumaHairIK:

    def ApplyIK(armature):

        isArmatureHidden = armature.hide_get()
        armature.hide_set(False)
        bpy.context.view_layer.objects.active = armature
        # Must Be Done in Pose Mode
        bpy.ops.object.mode_set(mode='POSE')

        for bone in armature.pose.bones:
            ik = bone.constraints.get("IK")
            if ik and ik.target:
                for col in ik.target.users_collection:
                    if col.name == "HAIR_IK":



                        ############################################
                        currentBone = bone
                        for i in range(ik.chain_count - 1):
                            
                            parentIK = (currentBone.parent.constraints.get("IK") or currentBone.parent.constraints.new("IK"))
                            parentIK.target = armature
                            parentIK.subtarget = currentBone.name
                            parentIK.chain_count = 1

                            databone = armature.data.bones[currentBone.parent.name]

                            bpy.context.object.data.bones.active = databone
                            bpy.ops.constraint.apply(constraint="IK", owner="BONE")

                            
                            currentBone = currentBone.parent
                        #######################################

                        bpy.context.object.data.bones.active = armature.data.bones[bone.name]
                        bpy.ops.constraint.apply(constraint="IK", owner="BONE")# This has no effect
                        

        # Exit Pose Mode
        bpy.ops.object.mode_set(mode='OBJECT')
        if isArmatureHidden:
            armature.hide_set(True)

    def CreateHairIKChain(armature):
        HAIR_NAME_PREFIX = 'J_Sec_Hair'    
        hairPattern = "(.*Hair.*)[0-9][0-9]"
        costumePattern = "(.*_end_)[0-9][0-9]"
        costumePatternSuffix = '[0-9]?[0-9]?(_end_)[0-9][0-9]'

        isArmatureHidden = armature.hide_get()
        armature.hide_set(False)
        bpy.context.view_layer.objects.active = armature

        # Must Be Done in Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')
        
        hairIKChainDict = {}
        costumeIKChainDict = {}
        for bone in armature.pose.bones:

            # Case Hair Bone
            if re.match(hairPattern, bone.name):
                chainIndex = bone.name[bone.name.rfind('_')+1:len(bone.name)]
                hairIKChain = (hairIKChainDict.get(chainIndex) or HairIKChain(chainIndex))

                # Update max length of chain
                chainLength = bone.name.replace(HAIR_NAME_PREFIX, '')
                chainLength = chainLength[0:chainLength.index('_')]
                hairIKChain.setMaxSegment(int(chainLength))
                
                hairIKChainDict[chainIndex] = hairIKChain

            # Case Costume
            elif re.match(costumePattern, bone.name):
                chainName = re.sub(costumePatternSuffix, '', bone.name)
                chainIndex = bone.name[bone.name.rfind('_')+1:len(bone.name)]
                costumeIKChain = (costumeIKChainDict.get(chainName)
                                or CostumeIKChain(chainName, bone.name[0:bone.name.rindex('_')]))
                costumeIKChain.addChainIndex(chainIndex)
                costumeIKChainDict[chainName] = costumeIKChain

        # Link Hair Chain
        for key in hairIKChainDict:
            ikChain:HairIKChain = hairIKChainDict[key]
            for i in range(2, ikChain.length + 1):
                parentBone = armature.data.edit_bones[HAIR_NAME_PREFIX + str(i-1) + '_' + key]
                bone = armature.data.edit_bones[HAIR_NAME_PREFIX + str(i) + '_' + key]
                bone.head = parentBone.tail
                bone.use_connect = True

        # Link Cloth Chain
        for ckey in costumeIKChainDict:
            costumeChain:CostumeIKChain = costumeIKChainDict[ckey]
            for chainIndex in costumeChain.chainIndexArray:
                bone = armature.data.edit_bones[costumeChain.endBoneName + "_" + chainIndex]
                lenthCount = 1
                while bone.parent and costumeChain.chainName in bone.parent.name:
                    bone.head = bone.parent.tail
                    bone.use_connect = True
                    bone = bone.parent
                    lenthCount = lenthCount + 1
                    costumeChain.setLength(lenthCount)

        # Set IK
        bpy.ops.object.mode_set(mode='POSE')

        # IK Hair Chain
        for key in hairIKChainDict:
            ikChain:HairIKChain = hairIKChainDict[key]
            tipBone = armature.pose.bones[HAIR_NAME_PREFIX + str(ikChain.length) + '_' + key]
            ik = (tipBone.constraints.get("IK") or tipBone.constraints.new("IK"))
            ik.chain_count = ikChain.length
            ik.target = QumaHairIK.createHairCostumeIKMarker(armature, tipBone, HAIR_NAME_PREFIX + ikChain.chainIndex)

        for ckey in costumeIKChainDict:
            costumeChain:CostumeIKChain = costumeIKChainDict[ckey]
            target = None
            for chainIndex in costumeChain.chainIndexArray:
                tipBone = armature.pose.bones[costumeChain.endBoneName + "_" + chainIndex]
                if target is None:
                    target = QumaHairIK.createHairCostumeIKMarker(armature, tipBone, costumeChain.chainName)
                ik = (tipBone.constraints.get("IK") or tipBone.constraints.new("IK"))
                ik.chain_count = costumeChain.length
                ik.target = target

        bpy.ops.object.mode_set(mode='OBJECT')
        if isArmatureHidden:
            armature.hide_set(True)

    def createHairCostumeIKMarker(armature, bone, markerName):
        MARKER_SIZE = 0.01
        COLLECT_NAME = "HAIR_IK"

        if bpy.data.objects.get(markerName) == None:

            # 1. Create Marker
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count = 8, radius=MARKER_SIZE)

            marker = bpy.context.object
            marker.name = markerName
            
            # 2. Create or get collection
            if bpy.data.collections.get(COLLECT_NAME) == None:
                collection = bpy.data.collections.new(COLLECT_NAME) 
                bpy.context.scene.collection.children.link(collection)
            else:
                collection = bpy.data.collections.get(COLLECT_NAME) 

            # 3. Put marker to collection           
            for coll in marker.users_collection:
                # Unlink the object
                coll.objects.unlink(marker)
            collection.objects.link(marker)
        else:
            marker = bpy.data.objects.get(markerName)
        
        # Align Marker
        marker.location = bone.tail
        marker.rotation_euler = (bone.matrix).to_euler()
        marker.parent = armature

        return marker

class HairIKChain:
    def __init__(self, chainIndex):
        self.chainIndex = chainIndex
        self.length = 0

    def setMaxSegment(self, segmentID):
        self.length = max(self.length, segmentID)


class CostumeIKChain:
    
    def __init__(self, chainName, endBoneName):
        self.chainName = chainName
        self.endBoneName = endBoneName
        self.length = 0
        self.chainIndexArray = []

    def addChainIndex(self, chainIndex):
        self.chainIndexArray.append(chainIndex)

    def setLength(self, length):
        self.length = max(self.length, length)
