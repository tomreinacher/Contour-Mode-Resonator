import shapely as sp
import gdsfactory as gf
from gdsfactory.generic_tech import get_generic_pdk

gf.clear_cache()
###################################
#General gds properties

originx = 0
originy = 0
metal_layer = (1,0)
resist_layer = (2,0)

###################################
#RF Probe pad dimensions 

pad_width = 100
pad_height = 50

arm_width = 15 #width of arm between pad and IDT

#####################################
#IDT properties

electrode_number = 100
electrode_length = 60
electrode_width = 0.25
electrode_separation = 0.25
electrode_end_margin = 10  #distance between bus and electrode of opposite potential

bus_width = 20 #width of metal electrode connecting idt fingers

def straight_idt(originx,originy,electrode_number,electrode_separation,electrode_width):
    c = gf.Component("pad_and_bus")
    t = gf.Component("Text")

    ################Add one bus + port###################
    bus_length = electrode_number*(electrode_width+electrode_separation)-electrode_separation #length of metal electrode connecting idt fingers

    bus = c.add_polygon(
        [(originx,originx,bus_width,bus_width),(originy,bus_length,bus_length,originy)],layer=metal_layer
    )
    c.add_port(
        name="bus_port",center=[0,bus_length/2],width=arm_width,orientation=180,layer=metal_layer #standard orientation of port is parallel to y axis
    )

    ##############Add one pad + port #######################
    pad_originx = originx-pad_width/2
    pad_originy = originy+2*bus_length 

    pad = c.add_polygon(
        [(pad_originx,pad_originx,pad_originx+pad_width,pad_originx+pad_width),(pad_originy,pad_originy+pad_height,pad_originy+pad_height,pad_originy)],layer=metal_layer
    )
    c.add_port(
        name="pad_port",center=[pad_originx+arm_width/2,pad_originy],width=arm_width,orientation=270,layer=metal_layer
    )

    ##########Get route between bus and pad#################

    route = gf.routing.get_route(c.ports["bus_port"], c.ports["pad_port"],width = arm_width)
    c.add(route.references)

    ##########Mirror bus and pad about center of IDT#############
    
    mirror_originx = originx+  bus_width + (electrode_length + electrode_end_margin)/2
    mirror_originy = originy + bus_length/2

    d = gf.Component("pad_and_bus_mirrored")
    bus_and_pad_1 = d << c
    bus_and_pad_2 = d << c
    bus_and_pad_2.mirror(p1=[mirror_originx,0],p2=[mirror_originx,mirror_originy])

    ##########Add IDT electrodes###########################

    electrodes = []

    for i in range(electrode_number):
        # Calculate x-coordinate for the current electrode
        x1 = originx + bus_width
        x2 = x1 + electrode_length
        y1 = originy + ((i)*(electrode_width+electrode_separation))
        y2 = y1 + electrode_width
        
        # Check if the current electrode should be offset
        if i % 2 == 1:
            x1 += electrode_end_margin  # Offset for every second electrode
            x2 += electrode_end_margin
        
        electrode_i = d.add_polygon([(x1,y1),(x1,y2),(x2,y2),(x2,y1)],layer = (1,0))
        electrodes.append(electrode_i)
        
    return d

component = gf.Component("straight_IDT")
component << straight_idt(originx,originy,100,electrode_separation,electrode_width)

component.write_gds("teststructures.gds")
component.show()