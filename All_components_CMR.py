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

arm_width= 15 #width of arm between pad and taper

########################################
#Etch window properties
etch_window_gap = 5
etch_buffer = 1 #distance between IDTs and etch window

#####################################
#Tether dimensions
tether_width = 5 #width of tether polygon
tether_length = etch_window_gap

taper_length = 20

#####################################
#IDT properties

electrode_number = 40
electrode_length = 60
electrode_width = 0.25
electrode_separation = 0.25
electrode_end_margin = 10  #distance between bus and electrode of opposite potential

bus_width = 5 #width of metal electrode connecting idt fingers

angle = 0 #angle of the entire CMR component - label 

######################################################################
#                      Flat-edge CMR Method                          #
######################################################################   
'''Instead of porting each individual IDT finger to the bus, a union is done between all metallized parts to create one solid metal layer component.
 The etch windows are also defined using unions instead of ports. The bus/pad and route are done using ports and defined more correctly.'''

def flat_cmr(originx,originy,electrode_number,electrode_separation,electrode_width,tether_width,angle):
    #c = gf.Component("pad_and_bus")
    
    ################Add one bus, tether, taper + port###################
    bus = gf.Component("bus")

    bus_length = electrode_number*(electrode_width+electrode_separation)-electrode_separation #length of metal electrode connecting idt fingers

    p1 = bus.add_polygon(
        [(originx,originx,bus_width,bus_width),(originy,bus_length,bus_length,originy)],layer=metal_layer
    )

    bus.add_port(
        name="bus_port",center=[originx,bus_length/2],width=tether_width,orientation=180,layer=metal_layer #standard orientation of port is parallel to y axis
    )

    tether = gf.Component("tether")

    p2 = tether.add_polygon(
        [(originx,originx,originx+tether_length,originx+tether_length),(originy,originy+tether_width,originy+tether_width,originy)]
    )
    
    tether.add_port(
        name="tether_port1",center=[originx,tether_width/2],width=tether_width,orientation=180,layer=metal_layer #standard orientation of port is parallel to y axis
    )
    tether.add_port(
        name="tether_port2",center=[originx+tether_length,tether_width/2],width=tether_width,orientation=0,layer=metal_layer #standard orientation of port is parallel to y axis
    )
    
    taper =  gf.components.taper(
        length = taper_length,
        width1 = arm_width,
        width2 = tether_width,
        with_two_ports = True,
        port_order_name = ("taper_port1","taper_port2"),
        layer = metal_layer
    )

    connect_parts = gf.Component("connect_parts")
    c1 = connect_parts << bus
    c2 = connect_parts << tether
    c3 = connect_parts << taper

    c2.connect("tether_port2",c1.ports["bus_port"])
    c3.connect("taper_port2",c2.ports["tether_port1"])

    taper_port_x = originx-tether_length-taper_length
    taper_port_y = bus_length/2

    #must add component-level reference to uderlying subcomponent port
    connect_parts.add_port(
       name="taper_port",port=c3.ports["taper_port1"] 
    )

    ##############Add one pad + port #######################
    pad = gf.Component("pad")
    
    pad_originx = originx-3*pad_width/4
    pad_originy = originy+2*29.75 #fixed height based on longest bus length with 60 fingers

    pad.add_polygon(
        [(pad_originx,pad_originx,pad_originx+pad_width,pad_originx+pad_width),(pad_originy,pad_originy+pad_height,pad_originy+pad_height,pad_originy)],layer=metal_layer
    )
    pad.add_port(
        name="pad_port",center=[pad_originx+arm_width/2,pad_originy],width=arm_width,orientation=270,layer=metal_layer
    )

    ##########Get route between bus and pad#################
    pad_and_bus = gf.Component("pad_and_bus")

    port1 = pad_and_bus << connect_parts
    port2 = pad_and_bus << pad

    route = gf.routing.get_route(
        port1.ports["taper_port"], 
        port2.ports["pad_port"],
        width = arm_width
    )
    pad_and_bus.add(route.references)

    ##########Mirror bus and pad about center of IDT#############
    mirror_originx = originx+  bus_width + (electrode_length + electrode_end_margin)/2
    mirror_originy = originy + bus_length/2

    pad_and_bus_complete = gf.Component("pad_and_bus_mirrored")
    bus_and_pad_1 = pad_and_bus_complete << pad_and_bus
    bus_and_pad_2 = pad_and_bus_complete << pad_and_bus
    bus_and_pad_2.mirror(p1=[mirror_originx,0],p2=[mirror_originx,mirror_originy])

    ##########Add IDT electrodes###########################
    idt_array = gf.Component("idt_electrodes")
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
        
        electrode_i = idt_array.add_polygon([(x1,y1),(x1,y2),(x2,y2),(x2,y1)],layer = (1,0))
        electrodes.append(electrode_i)
    
    union_component = gf.Component("complete_component")
    union_component << pad_and_bus_complete
    union_component << idt_array
    union_component = gf.geometry.union(union_component, by_layer=False, layer=metal_layer)

    ################Create etch windows#######################
    etch_window = gf.Component("etch_window") #define top etch window subcomponents

    etch_window_length = 2*bus_width + electrode_length + electrode_end_margin + 2*(etch_buffer + etch_window_gap) #horizontal window length
    etch_window_height = bus_length/2 - tether_width/2 #vertical window length
    
    top_x1 = originx-(etch_buffer + etch_window_gap)
    top_x2 = top_x1 + etch_window_length
    top_y1 = bus_length + etch_buffer
    top_y2 = top_y1 + etch_window_gap

    left_x1 = originx - etch_window_gap - etch_buffer
    left_x2 = left_x1 + etch_window_gap
    left_y1 = bus_length/2 + tether_width/2 + etch_buffer
    left_y2 = left_y1 + etch_window_height

    right_x1 = originx + 2*bus_width + electrode_length + electrode_end_margin + etch_buffer
    right_x2 = right_x1 + etch_window_gap
    right_y1 = bus_length/2 + tether_width/2 + etch_buffer
    right_y2 = right_y1 + etch_window_height

    #union acting weird and only taking two arguments so I have to make this dodgy fix and do two unions, sorry 
    
    etch_window_union1 = gf.Component("etch_window_union") #make union so there is one continuous top etch window
    top_window = etch_window_union1.add_polygon([(top_x1,top_y1),(top_x1,top_y2),(top_x2,top_y2),(top_x2,top_y1)],layer=resist_layer)
    left_window = etch_window_union1.add_polygon([(left_x1,left_y1),(left_x1,left_y2),(left_x2,left_y2),(left_x2,left_y1)],layer=resist_layer)
    etch_window_union1 = gf.geometry.union(etch_window_union1, by_layer=False, layer=resist_layer)

    etch_window_union2 = gf.Component("etch_window_union2") #make union so there is one continuous top etch window
    etch_window_union2 << etch_window_union1
    right_window = etch_window_union2.add_polygon([(right_x1,right_y1),(right_x1,right_y2),(right_x2,right_y2),(right_x2,right_y1)],layer=resist_layer)
    etch_window_union2 = gf.geometry.union(etch_window_union2, by_layer=False, layer=resist_layer)

    etch_window_complete = gf.Component("etch_window_complete") #mirror top etch window so there are two etch windows top and bottom
    
    mirror_originx = originx 
    mirror_originy = originy + bus_length/2
    mirror_p1 = mirror_originx + etch_window_length/2
    
    top_window = etch_window_complete << etch_window_union2
    bottom_window = etch_window_complete << etch_window_union2
    bottom_window.mirror(p1=[mirror_originx,mirror_originy],p2=[mirror_p1,mirror_originy])

    ###########Make component including etch windows and CMR and rotate if necessary##################
    CMR_component = gf.Component("CMR_component")
    CMR_component << union_component
    CMR_component << etch_window_complete
    CMR_component.rotate(45) 


    ############Create label for flat-edge CMR###################
    label = gf.Component("label")
    text = f"Pair num = {electrode_number/2}\nPeriod = {2*(electrode_width+electrode_separation)}\nTether w = {tether_width+2*etch_buffer}"
    
    label_contents = label << gf.components.text(
        text=text,
        size=5,
        position=[originx - 3*pad_width/4, originy - 15],
        justify='left',
        layer=metal_layer
    )

    #########Define final flat-edge CMR component#############
    final_component = gf.Component("final_component")
    final_component << CMR_component
    final_component << label

    return final_component


all_components = gf.Component("flat_CMR")
c1 = all_components << flat_cmr(originx,originy,20,electrode_separation,electrode_width,tether_width,angle)
c2 = all_components << flat_cmr(originx,originy,40,electrode_separation,electrode_width,10,45)
c3 = all_components << flat_cmr(originx,originy,60,electrode_separation,electrode_width,10,45)

c2.move([300,0])
c3.move([600,0])

all_components.write_gds("all_components.gds")
all_components.show()