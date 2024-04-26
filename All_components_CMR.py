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
tether_length = etch_window_gap + etch_buffer

taper_length = 20

#####################################
#IDT properties

electrode_number = 40
electrode_length = 60
electrode_width = 0.25
electrode_separation = 0.25
electrode_end_margin = 10  #distance between bus and electrode of opposite potential

bus_width = 5 #width of metal electrode connecting idt fingers
bus_length = electrode_number*(electrode_width+electrode_separation)-electrode_separation 

angle = 0 #angle of the entire CMR component - label #DOESN'T WORK
k = etch_window_gap/2 #curvature factor, r2 of ellipse used to construct curved etch window

radius = 25 #outer radius of undercut ring test structure
width = 20 #width of test ring

undercut = True #define if undercut is to be used or not, for debug structures

######################################################################
#                      Flat-edge CMR Method                          #
######################################################################   
'''Instead of porting each individual IDT finger to the bus, a union is done between all metallized parts to create one solid metal layer component.
 The etch windows are also defined using unions instead of ports. The bus/pad and route are done using ports and defined more correctly.'''

def flat_cmr(destinationx,destinationy,electrode_number,electrode_separation,electrode_width,tether_width,angle,undercut):
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
    if undercut:
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
    if undercut:
        CMR_component << etch_window_complete
    CMR_component.rotate(angle)


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
    CMR_and_label = gf.Component("final_component")
    CMR_and_label << CMR_component
    CMR_and_label << label

    final_component = gf.Component("final_component")
    fc = final_component << CMR_and_label
    fc.move(origin=[originx,originy],destination=[destinationx,destinationy])

    return final_component


######################################################################
#                      Biconvex-edge CMR Method                      #
######################################################################   
'''The curvature is defined by subtracting an ellipse with two radii r1,r2 from a rectangle. 
That means adding curvature adds area to the resonator and substracts area from the etch window.'''

def biconvex_cmr(destinationx,destinationy,electrode_number,electrode_separation,electrode_width,tether_width,angle,k):
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

    #must add component-level reference to underlying subcomponent port
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

    ################Create top curved etch window#######################
    #method:subtract ellipse with radii r1,r2 from rectangle to create curved edge

    etch_window_length = 2*bus_width + electrode_length + electrode_end_margin + 2*etch_buffer #horizontal window length
    etch_window_height = bus_length/2 - tether_width/2 + etch_window_gap #vertical window length

    E = gf.components.ellipse(radii=(etch_window_length/2, k), layer=(1, 0))
    R = gf.components.rectangle(size=[etch_window_length, etch_window_gap], layer=(2, 0))
    bool = gf.Component("bool")
    E_ref = bool << E
    E_ref.movex(etch_window_length/2)
    R_ref = bool << R 
    bool_obj = gf.geometry.boolean(A=R_ref, B=E_ref, operation="not", precision=1e-6, layer=(3, 0))

    bool = gf.Component("bool")
    bool << bool_obj
    bool.add_port(
        name="tw1",center=[originx,etch_window_gap/2],width=etch_window_gap,layer=resist_layer
    )
    bool.add_port(
        name="tw2",center=[originx+etch_window_length,etch_window_gap/2],width=etch_window_gap,layer=resist_layer
    )

    ##############Adding left and right lateral etch windows with ports##############

    left_x1 = originx - etch_window_gap - etch_buffer
    left_x2 = left_x1 + etch_window_gap
    left_y1 = bus_length/2 + tether_width/2 + etch_buffer
    left_y2 = left_y1 + etch_window_height

    right_x1 = originx + 2*bus_width + electrode_length + electrode_end_margin + etch_buffer
    right_x2 = right_x1 + etch_window_gap
    right_y1 = bus_length/2 + tether_width/2 + etch_buffer
    right_y2 = right_y1 + etch_window_height

    left_window = gf.Component("left_window")
    lw = left_window.add_polygon([(left_x1,left_y1),(left_x1,left_y2),(left_x2,left_y2),(left_x2,left_y1)],layer=resist_layer)
    left_window.add_port(
        name="lw",center=[left_x2,left_y2-etch_window_gap/2],width=etch_window_gap,layer=resist_layer
    )

    right_window = gf.Component("right_window")
    rw = right_window.add_polygon([(right_x1,right_y1),(right_x1,right_y2),(right_x2,right_y2),(right_x2,right_y1)],layer=resist_layer)
    right_window.add_port(
        name="rw",center=[right_x1,right_y2-etch_window_gap/2],width=etch_window_gap,layer=resist_layer
    )

    ###########Assembling top and lateral windows and making union###########
    top_window = gf.Component("top_window")
    c1 = top_window << bool
    c2 = top_window << left_window
    c3 = top_window << right_window

    c1.connect("tw1",c2.ports["lw"])
    c1.connect("tw2",c3.ports["rw"])

    etch_window_complete = gf.Component("etch_window_complete") #mirror top etch window so there are two etch windows top and bottom
    
    mirror_originx = originx 
    mirror_originy = originy + bus_length/2
    mirror_p1 = mirror_originx + etch_window_length/2
    
    top_etch_window = etch_window_complete << top_window
    bottom_etch_window = etch_window_complete << top_window
    bottom_etch_window.mirror(p1=[mirror_originx,mirror_originy],p2=[mirror_p1,mirror_originy])

    etch_window_union = gf.Component("etch_window_union") #make union so there is one continuous top etch window
    etch_window_union << etch_window_complete
    etch_window_union = gf.geometry.union(etch_window_complete, by_layer=False, layer=resist_layer)

    ###########Make component including etch windows and CMR and rotate if necessary##################
    CMR_component = gf.Component("CMR_component")
    CMR_component << union_component
    CMR_component << etch_window_union
    CMR_component.rotate(angle)


    ############Create label for biconvex-edge CMR###################
    label = gf.Component("label")
    text = f"Pair num = {electrode_number/2}\nPeriod = {2*(electrode_width+electrode_separation)}\nTether w = {tether_width+2*etch_buffer}\nk = {k}"
    
    label_contents = label << gf.components.text(
        text=text,
        size=5,
        position=[originx - 3*pad_width/4, originy - 15],
        justify='left',
        layer=metal_layer
    )

    #########Define final biconvex-edge CMR component#############
    CMR_and_label = gf.Component("CMR and label")
    CMR_and_label << CMR_component
    CMR_and_label << label

    final_component = gf.Component("final_component")
    fc = final_component << CMR_and_label
    fc.move(origin=[originx,originy],destination=[destinationx,destinationy])
    
    return final_component

###########################################################
#            Undercut Test Structures Method              #
###########################################################

def undercut_ring(destinationx,destinationy,radius,width):
    #radius is center radius of ring between inner radius and outer radius
    radius = 25 - width/2 

    tether_width = 10
    tether_length = etch_window_gap + etch_buffer

    left_port_x = originx-radius-width/2+0.5
    left_port_y = originy

    right_port_x = originx+radius+width/2-0.5
    right_port_y = originy

    ring =gf.Component("ring")
    c1 = ring << gf.components.ring(radius=radius, width=width, angle_resolution=2.5, layer=metal_layer)
    ring.add_port(
        name="left_port", center=[left_port_x,left_port_y], width=tether_width, orientation=180, layer=metal_layer
    )
    ring.add_port(
        name="right_port", center=[right_port_x,right_port_y], width=tether_width, orientation=0, layer=metal_layer
    )

    left_tether = gf.Component("left_tether")
    t1 = left_tether.add_polygon(
        [(originx,originx,originx+tether_length,originx+tether_length),(originy,originy+tether_width,originy+tether_width,originy)]
    )
    left_tether.add_port(
        name="lp", center=[originx+tether_length,originy+tether_width/2], width=tether_width, orientation=0, layer=metal_layer
    )

    right_tether = gf.Component("right_tether")
    t1 = right_tether.add_polygon(
        [(originx,originx,originx+tether_length,originx+tether_length),(originy,originy+tether_width,originy+tether_width,originy)]
    )
    right_tether.add_port(
        name="rp", center=[originx,originy+tether_width/2], width=tether_width, orientation=180, layer=metal_layer
    )

    ring_and_tethers = gf.Component("ring_and_tethers")
    r = ring_and_tethers << ring
    lt = ring_and_tethers << left_tether
    rt = ring_and_tethers << right_tether
    lt.connect("lp", r.ports["left_port"])
    rt.connect("rp",r.ports["right_port"])
    
    tethered_ring = gf.Component("tethered_ring")
    tethered_ring << gf.geometry.union(ring_and_tethers, layer=metal_layer)
    
    #get bound box
    boundary = gf.Component("boundary")
    boundary << tethered_ring
    p1 = boundary.get_polygon_bbox(top=3, bottom=3)
    p2 = boundary.add_polygon(p1, layer=resist_layer)

    difference_resist = gf.Component("difference")
    R = difference_resist << tethered_ring
    P = difference_resist << boundary
    difference_box = gf.geometry.boolean(A=P, B=R, operation="not", precision=1e-6, layer=resist_layer)

    ring_and_resist = gf.Component("ring_and_resist")
    fc = ring_and_resist << difference_box

    fc.move(origin=[originx,originy],destination=[destinationx,destinationy])

    return ring_and_resist

#####################################################
#            Alignment Marker Method                #
#####################################################    

def alignment_marker(originx,originy):
    
    alignment = gf.Component("alignment_2")  
   
    corner_1 = alignment.add_ref(gf.components.L(width=0.5, size=[1, 1], layer=(1,0)))
    corner_1.move(destination = (originx,originy))
    corner_2 = alignment.add_ref(gf.components.L(width=1, size=[3, 3], layer=(1,0)))
    corner_2.move(destination = (originx-5,originy-5)) 
    corner_3 = alignment.add_ref(gf.components.L(width=2, size=[6, 6], layer=(1,0)))
    corner_3.move(destination = (originx-13,originy-13)) 
    corner_4 = alignment.add_ref(gf.components.L(width=2, size=[12, 12], layer=(1,0)))
    corner_4.move(destination = (originx-25,originy-25))  
    corner_5 = alignment.add_ref(gf.components.L(width=2, size=[24, 24], layer=(1,0)))
    corner_5.move(destination = (originx-45,originy-45))  
    corner_6 = alignment.add_ref(gf.components.L(width=2, size=[50, 50], layer=(1,0)))
    corner_6.move(destination = (originx-105,originy-105)) 
    corner_7 = alignment.add_ref(gf.components.L(width=2, size=[100, 100], layer=(1,0)))
    corner_7.move(destination = (originx-205,originy-205))  
    corner_box =  alignment.add_polygon(points = [(originx-235, originy-235),(originx-235,originy-215),(originx-215,originy-215),(originx-215,originy-235)], layer = metal_layer)
    
    mirror1 = alignment.mirror(p1 = (originx+5,originy), p2 = (originx+5,originy+1))
    mirror2 = mirror1.mirror(p1 = (originx,originy+5), p2 = (originx+1,originy+5))
    mirror3 = mirror2.mirror(p1 = (originx+5,originy), p2 = (originx+5,originy+1))
    
    cross = alignment.add_ref(gf.components.align_wafer(width=0.2, spacing=1.5, cross_length=3, layer=metal_layer, square_corner='bottom_left'))
    cross.move(destination = (originx+5,originy+5))

    align_component = gf.Component("all corners")
    align_component << alignment
    align_component << mirror1
    align_component << mirror2
    align_component << mirror3
    return align_component

#############################################################################
#             Create grid with parametric sweep                             #
#############################################################################
components_list = []
for w in [2.5,5,10,15,20]:
    A = undercut_ring(originx,originy,radius,w)
    components_list.append(A)
for t in [1.25,2.5,5,10,bus_length]:
    C = flat_cmr(originx,originy,electrode_number,electrode_separation,electrode_width,t,angle,undercut)
    components_list.append(C)
for r in [0.5,1,1.5,2,2.5]:
    for t in [1.25,2.5,5,10,bus_length]:
        B = biconvex_cmr(originx,originy,electrode_number,electrode_separation,electrode_width,t,angle,r)
        components_list.append(B)
components_list.append(flat_cmr(originx,originy,electrode_number,0.125,0.125,tether_width,angle,False))
components_list.append(flat_cmr(originx,originy,electrode_number,electrode_separation,electrode_width,tether_width,45,False))
components_list.append(flat_cmr(originx,originy,electrode_number,electrode_separation,electrode_width,tether_width,angle,False))
components_list.append(flat_cmr(originx,originy,electrode_number,electrode_separation,electrode_width,tether_width,45,undercut))
components_list.append(flat_cmr(originx,originy,electrode_number,0.375,0.375,tether_width,angle,False))


grid = gf.grid(
    components_list,
    spacing =(20,20),
    separation=True,
    shape=(8,5),
    align_x="x",
    align_y="y",
    edge_x="x",
    edge_y="ymax"
)

all_components = gf.Component("all_components")
all_components << grid
all_components << alignment_marker(1400,1400)
all_components << alignment_marker(1400,-300)
all_components << alignment_marker(-350,1400)
all_components << alignment_marker(-350,-300)


all_components.write_gds("all_components.gds")
all_components.show()