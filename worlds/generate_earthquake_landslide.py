#!/usr/bin/env python3
"""Repair original disaster-scene mesh materials and create seeded SDF variants."""
from pathlib import Path
import math, random, argparse, json
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parent
ASSET = ROOT / 'earthquake_landslide_assets'
MESH = ASSET / 'meshes'
TEX = ASSET / 'materials' / 'textures'
W, H, N = 180.0, 150.0, 769

PALETTE = {
    'concrete': (.48,.46,.41), 'dark_concrete': (.32,.34,.34),
    'brick': (.49,.25,.17), 'roof': (.34,.19,.14), 'steel': (.16,.19,.20),
    'wood': (.34,.24,.14), 'stone': (.43,.42,.37), 'plaster': (.62,.57,.46),
}

def river_x(y):
    """Curved stream centerline shared by terrain, texture and river mesh."""
    return -8.0 - .47*y + 2.7*math.sin(y/11.5) + 1.2*math.sin(y/4.4+.6)

# Scenario height profiles: deterministic, broad valley with flank ridges.
def height(x, y, mode):
    # Curving stream valley runs from upper-left toward lower-right.
    cx = river_x(y)
    d = x - cx
    valley = 1.8 + 1.8*(1-math.exp(-(d/22.0)**2))
    # A narrow incised channel and a low gravel shelf make the stream visible
    # against the raster terrain rather than burying a water plane underground.
    valley -= 1.5*math.exp(-(d/5.0)**2)
    east_ridge = 34.0 / (1.0 + math.exp(-(x - (40.0 + .18*y))/8.5))
    west_ridge = 23.0 * math.exp(-((x+82.0)/17.0)**2)
    north_ridge = 13.0 * math.exp(-((y-68.0)/17.0)**2)
    south_ridge = 10.0 * math.exp(-((y+72.0)/18.0)**2)
    # Interference noise at mixed, oblique scales avoids the old parallel bands.
    hills = (1.8*math.sin(.17*x+.13*y)*math.sin(.11*x-.19*y)
             + .9*math.sin(.43*x+.29*y)*math.sin(.37*y-.23*x)
             + .35*math.sin(.91*x-.77*y)*math.sin(.63*x+.82*y))
    z = valley + east_ridge + west_ridge + north_ridge + south_ridge + hills
    # Landslide scar carved through the eastern mountainside, with toe/runout.
    if mode in ('landslide', 'combined'):
        scarline = 63.0 + .28*y
        scar = math.exp(-((x-scarline)/11.5)**2) * math.exp(-((y-4.0)/48.0)**4)
        z -= 14.0*scar
        toe = math.exp(-(((x-40.0)/18.0)**2 + ((y+17.0)/24.0)**2))
        z += 5.2*toe
    # Earthquake-only collapse is mostly settlement; terrain has minor ground rupture.
    if mode in ('earthquake', 'combined'):
        rupture = math.exp(-(((x+22.0)/3.2)**2 + ((y-3.0)/42.0)**2))
        z -= 1.8*rupture
    # Taper the surface to a clean, level perimeter instead of ending on a ridge.
    edge = min(90.0-abs(x), 75.0-abs(y))
    ef = max(0.0,min(1.0,edge/9.0)); ef=ef*ef*(3-2*ef)
    z = 2.0 + (z-2.0)*ef
    # Repeatable flat assembly apron, clipped to gentle elevations.
    apron_r = math.sqrt((x+70.0)**2 + (y+56.0)**2)
    blend = max(0.0, min(1.0, (apron_r-10.0)/9.0))
    z = 1.5*(1-blend) + z*blend
    return max(0.4, min(48.0, z))

def make_terrain(mode):
    print(f'Generating {mode} terrain heightmap ({N}x{N})...', flush=True)
    im = Image.new('L', (N,N)); px=im.load()
    vals=[]
    for j in range(N):
        y=75.0 - j*H/(N-1)
        for i in range(N):
            x=-90.0 + i*W/(N-1)
            z=height(x,y,mode)
            # Height is encoded 0..50m; SDF size.z maps it to vertical scale.
            v=max(0,min(255,round(z/50.0*255)))
            px[i,j]=v
    im.save(MESH/f'terrain_{mode}.png', optimize=True)
    print(f'  wrote terrain_{mode}.png', flush=True)

def make_texture(mode):
    print(f'Generating {mode} terrain texture...', flush=True)
    rng=random.Random(82731); n=768
    fine=Image.effect_noise((256,256),100).resize((n,n),Image.BICUBIC).load()
    broad=Image.effect_noise((64,64),100).resize((n,n),Image.BICUBIC).load()
    im=Image.new('RGB',(n,n)); p=im.load()
    for j in range(n):
        y=75 - j*150/(n-1)
        for i in range(n):
            x=-90 + i*180/(n-1)
            z=height(x,y,mode)
            cx=river_x(y); d=abs(x-cx)
            # Continuous elevation blend: green valley -> scrub -> exposed rock.
            t=max(0.0,min(1.0,(z-16.0)/18.0)); t=t*t*(3-2*t)
            low=(79,116,72); high=(133,128,115)
            coarse=(broad[i,j]-128)/128; detail=(fine[i,j]-128)/128
            rough=8*coarse+5*detail+rng.randint(-3,3)
            base=[low[k]*(1-t)+high[k]*t for k in range(3)]
            # A diffuse sinuous gravel bank; water itself is a separate curved mesh.
            bank=max(0.0,1.0-abs(d-4.5)/3.4)
            for k,gravel in enumerate((132,121,99)):
                base[k]=base[k]*(1-.72*bank)+gravel*(.72*bank)
            # Organic scar mask: feathered ends, irregular edges, and mixed soil/rock.
            if mode in ('landslide','combined'):
                scarline=63.0+.28*y+2.3*math.sin(y/13.0)
                along=math.exp(-((y-3.0)/50.0)**4)
                jitter=1.0+.23*coarse+.1*math.sin(1.7*x+.6*y)
                scar=math.exp(-(((x-scarline)/(12.5*jitter))**2))*along
                scar=max(0.0,min(.94,scar))
                rockmix=max(0.0,min(1.0,.47+.30*coarse+.18*detail))
                soil=(151,105,69); rock=(131,126,116)
                scarcolor=[soil[k]*(1-rockmix)+rock[k]*rockmix for k in range(3)]
                base=[base[k]*(1-scar)+scarcolor[k]*scar for k in range(3)]
            p[i,j]=tuple(max(0,min(255,round(c+rough))) for c in base)
    im.save(TEX/f'terrain_albedo_{mode}.png', optimize=True)
    # Neutral normal map; terrain normals are derived from heightmap itself.
    Image.new('RGB',(4,4),(128,128,255)).save(TEX/'terrain_normal.png')
    print(f'  wrote terrain_albedo_{mode}.png', flush=True)

def make_surface_textures():
    """Build small tiling albedo maps for the broken structure materials."""
    n=128
    for mat,base in PALETTE.items():
        rng=random.Random(771+sum(map(ord,mat))); im=Image.new('RGB',(n,n)); pix=im.load()
        for y in range(n):
            for x in range(n):
                variation=rng.randint(-15,15)+round(7*math.sin(x*.23+y*.11)+5*math.sin(y*.47-x*.17))
                color=list(base)
                if mat=='brick':
                    row=y//16; xx=(x+(row%2)*16)%32
                    color=[.31,.29,.25] if y%16<2 or xx<2 else [.54,.25,.16]
                elif mat=='roof':
                    color=[.25,.17,.13] if y%20<2 or (x+(y//20%2)*10)%20<2 else [.47,.22,.14]
                elif mat=='steel' and (x*7+y*13)%97<2:
                    color=[.48,.43,.31]
                elif mat=='wood':
                    variation+=round(14*math.sin(y*.52+math.sin(x*.09)))
                elif mat in ('concrete','dark_concrete','stone','plaster') and (x*17+y*29)%211<2:
                    variation-=22
                pix[x,y]=tuple(max(0,min(255,round(c*255+variation))) for c in color)
        im.save(TEX/f'surface_{mat}.png',optimize=True)

def box_faces(cx,cy,cz,sx,sy,sz, yaw=0.0):
    # Yaw-rotated cuboid faces. Vertices are appended without indexing concerns.
    ca,sa=math.cos(yaw),math.sin(yaw)
    verts=[]
    for z in (-sz/2,sz/2):
        for y in (-sy/2,sy/2):
            for x in (-sx/2,sx/2):
                verts.append((cx+x*ca-y*sa, cy+x*sa+y*ca, cz+z))
    # index order for bottom/top/front/back/left/right
    inds=[(1,3,2,0),(4,5,7,6),(0,2,6,4),(1,5,7,3),(0,4,5,1),(2,3,7,6)]
    return [tuple(verts[k] for k in face) for face in inds]

def _write_obj_single(name, parts):
    mats={mat:PALETTE.get(mat,(.5,.5,.5)) for _,_,_,mat in parts}
    (MESH/f'{name}.mtl').write_text(''.join(f'newmtl {m}\nKa {c[0]} {c[1]} {c[2]}\nKd {c[0]} {c[1]} {c[2]}\nKs 0.08 0.08 0.08\nmap_Kd ../materials/textures/surface_{m}.png\n' for m,c in mats.items()))
    lines=[f'mtllib {name}.mtl']; vcount=1; vtcount=1
    for (cx,cy,cz),(sx,sy,sz),yaw,mat in parts:
        lines.append(f'usemtl {mat}')
        faces=box_faces(cx,cy,cz,sx,sy,sz,yaw)
        # Duplicate vertices per face and assign metre-scaled UVs for tiled maps.
        for face in faces:
            for x,y,z in face: lines.append(f'v {x:.4f} {y:.4f} {z:.4f}')
            ulen=math.dist(face[0],face[1])*.65; vlen=math.dist(face[0],face[3])*.65
            for uv in ((0,0),(ulen,0),(ulen,vlen),(0,vlen)):
                lines.append(f'vt {uv[0]:.5f} {uv[1]:.5f}')
            lines.append('f '+' '.join(f'{v}/{vt}' for v,vt in zip(range(vcount,vcount+4),range(vtcount,vtcount+4))))
            vcount+=4; vtcount+=4
    (MESH/f'{name}.obj').write_text('\n'.join(lines)+'\n')

def write_obj(name, parts):
    """Write an aggregate OBJ and one color-isolated OBJ per material.

    Gazebo versions differ in whether an OBJ's MTL is honored by the renderer.
    The per-material variants let the SDF set explicit colors as a fallback.
    """
    _write_obj_single(name,parts)
    for mat in sorted({p[3] for p in parts}):
        _write_obj_single(f'{name}_{mat}',[p for p in parts if p[3]==mat])

def write_irregular_rubble():
    """Create a low-poly fractured pile, then export each material separately."""
    rng=random.Random(209); bymat={m:[] for m in ('concrete','dark_concrete','brick','stone')}
    for _ in range(28):
        cx,cy=rng.uniform(-4.8,4.8),rng.uniform(-3.8,3.8)
        rx,ry=rng.uniform(.45,1.35),rng.uniform(.4,1.15)
        n=rng.randint(5,7); phase=rng.random()*math.tau; lift=rng.uniform(.1,.5)
        bottom=[]; top=[]
        for j in range(n):
            a=phase+math.tau*j/n; fuzz=rng.uniform(.75,1.25)
            bottom.append((cx+rx*fuzz*math.cos(a),cy+ry*fuzz*math.sin(a),lift))
            top.append((cx+rx*rng.uniform(.5,1.05)*math.cos(a+.08),cy+ry*rng.uniform(.5,1.05)*math.sin(a+.08),lift+rng.uniform(.35,1.4)))
        mat=rng.choice(tuple(bymat))
        vs=bottom+top+[(cx,cy,lift-.04),(cx,cy,lift+rng.uniform(.45,1.3))]
        faces=[]
        for j in range(n):
            k=(j+1)%n
            faces.extend([(j+1,k+1,n+k+1),(j+1,n+k+1,n+j+1),
                          (2*n+1,j+1,k+1),(2*n+2,n+j+1,n+k+1)])
        bymat[mat].append((vs,faces))
    for mat, chunks in bymat.items():
        lines=[f'mtllib rubble_cluster_{mat}.mtl','usemtl '+mat]; base=1
        for verts,faces in chunks:
            for x,y,z in verts:
                lines.append(f'v {x:.4f} {y:.4f} {z:.4f}')
                lines.append(f'vt {x*.75:.5f} {y*.75:.5f}')
            lines.extend('f '+' '.join(f'{base+i-1}/{base+i-1}' for i in face) for face in faces)
            base += len(verts)
        (MESH/f'rubble_cluster_{mat}.obj').write_text('\n'.join(lines)+'\n')
        c=PALETTE[mat]
        (MESH/f'rubble_cluster_{mat}.mtl').write_text(f'newmtl {mat}\nKa {c[0]} {c[1]} {c[2]}\nKd {c[0]} {c[1]} {c[2]}\nKs .06 .06 .06\nmap_Kd ../materials/textures/surface_{mat}.png\n')

def create_meshes():
    # Structural, deliberately broken exposed-frame 4-storey apartment; local origin at ground.
    p=[]
    # slabs with missing corners and a dropped roof slab
    for z in (1.0,4.0,7.0,10.0):
        p += [((0,0,z),(10,8,.38),0,'concrete'), ((-3.3,0,z+.04),(3.2,8,.12),0,'dark_concrete')]
        for x in (-4.6,0,4.6):
            for y in (-3.6,3.6): p.append(((x,y,z+1.4),(.32,.32,2.8),0,'concrete'))
        # exposed diagonal steel braces
        for x in (-4.35,4.35):
            p.append(((x,0,z+1.25),(.18,7.0,2.25),.22 if x<0 else -.22,'steel'))
        # partial brick infill
        p += [((-2.2,-3.82,z+1.0),(4.0,.18,1.7),0,'brick'), ((4.55,1.6,z+1.0),(.18,3.2,1.8),0,'plaster')]
    p.append(((1.2,0,12.1),(7.8,6.8,.42),-.16,'roof'))
    p.append(((5.8,-1.8,8.5),(4.5,.3,.25),.55,'steel'))
    write_obj('collapsed_apartment',p)
    # Partially buried village house with a broken pitched-roof approximation.
    p=[((0,0,1.0),(7.0,6.0,1.7),0,'plaster'), ((-1.8,0,2.2),(3.1,5.8,1.4),0,'brick'),
       ((0,-2.5,3.0),(7.0,.22,.18),0,'wood'), ((0,0,3.0),(7.4,3.4,.25),.16,'roof'),
       ((-2.0,0,4.0),(3.8,.22,2.0),0,'wood'), ((2.2,2.2,1.9),(3.2,.26,.25),-.42,'concrete')]
    write_obj('buried_village_house',p)
    # Intact background houses for landslide-only runs (the slide, not quake, is varied).
    p=[((0,0,1.4),(7.0,6.0,2.8),0,'plaster'),
       ((0,-3.0,1.5),(7.0,.18,2.9),0,'plaster'), ((-3.5,0,1.5),(.18,6.0,2.9),0,'plaster'),
       ((0,0,3.0),(7.8,3.7,.28),.30,'roof'), ((0,0,3.0),(7.8,3.7,.28),-.30,'roof'),
       ((0,-3.12,1.25),(1.2,.08,1.7),0,'wood')]
    write_obj('intact_village_house',p)
    # Broken bridge span, central gap, exposed girders and collapsed end panels.
    p=[]
    p += [((-8,0,5),(13,6,.6),0,'concrete'), ((8,0,5),(11,6,.6),0,'concrete')]
    for y in (-2.5,2.5):
        p += [((-8,y,4.55),(13,.22,.32),0,'steel'), ((8,y,4.55),(11,.22,.32),0,'steel')]
    p += [((-7,-.6,1.8),(.8,.8,5.8),0,'concrete'), ((7,.6,1.8),(.8,.8,5.8),0,'concrete'),
          ((1.5,0,2.1),(4.0,.5,.45),-.42,'concrete'), ((11,2.3,2.3),(4.0,.4,.35),.65,'steel')]
    write_obj('damaged_bridge',p)
    # Fractured, triangulated masonry plus snapped reinforcing beams.
    write_irregular_rubble()
    beams=[]; rng=random.Random(816)
    for _ in range(9):
        beams.append(((rng.uniform(-3.8,3.8),rng.uniform(-3.2,3.2),rng.uniform(.55,1.7)),
                      (rng.uniform(2.4,5.5),.13,.13),rng.uniform(-1.1,1.1),'steel'))
    write_obj('rubble_beams',beams)
    # One irregular low-poly boulder mesh; instances use spheres for collision.
    rng=random.Random(445); verts=[]
    for z in (-1,1):
        for k in range(7):
            a=2*math.pi*k/7; r=rng.uniform(.78,1.18)
            verts.append((r*math.cos(a),r*math.sin(a),z*rng.uniform(.68,1.12)))
    verts.extend([(0.0,0.0,1.2),(0.0,0.0,-1.0)])
    # Triangulated bipyramid-ish rock using triangles across ring + top/bottom faces.
    lines=['mtllib irregular_boulder.mtl','usemtl stone']
    for x,y,z in verts:
        lines.append(f'v {x:.4f} {y:.4f} {z:.4f}')
        lines.append(f'vt {(math.atan2(y,x)+math.pi)/(2*math.pi):.5f} {(z+1.0)/2.2:.5f}')
    for i in range(7):
        j=(i+1)%7
        lines += [f'f {i+1}/{i+1} {j+1}/{j+1} {j+8}/{j+8}', f'f {i+1}/{i+1} {j+8}/{j+8} {i+8}/{i+8}']
        lines += [f'f 15/15 {i+8}/{i+8} {j+8}/{j+8}', f'f 16/16 {j+1}/{j+1} {i+1}/{i+1}']
    (MESH/'irregular_boulder.obj').write_text('\n'.join(lines)+'\n')
    (MESH/'irregular_boulder.mtl').write_text('newmtl stone\nKa .38 .37 .34\nKd .48 .46 .41\nKs .05 .05 .05\n')
    write_river_mesh()

def write_river_mesh():
    """Write a smooth, meandering, terrain-conforming water surface mesh."""
    lines=['mtllib river_surface.mtl','usemtl water']; n=320; base_y=72.0; span=144.0
    for row in range(n+1):
        y=base_y-span*row/n; cx=river_x(y)
        deriv=(river_x(y+.05)-river_x(y-.05))/.10
        nx=1.0/math.sqrt(1+deriv*deriv); ny=-deriv*nx
        half=2.25+0.48*math.sin(y*.13)+0.22*math.sin(y*.39)
        for side in (-1,1):
            x=cx+side*nx*half; yy=y+side*ny*half
            z=height(x,yy,'combined')+.14+.035*math.sin(.9*y+side)
            lines.append(f'v {x:.4f} {yy:.4f} {z:.4f}')
    for row in range(n):
        a=2*row+1; b=a+1; c=a+2; d=a+3
        lines.extend((f'f {a} {b} {d}',f'f {a} {d} {c}'))
    (MESH/'river_surface.obj').write_text('\n'.join(lines)+'\n')
    (MESH/'river_surface.mtl').write_text('newmtl water\nKa .08 .28 .38\nKd .10 .38 .52\nKs .4 .4 .4\nNs 80\n')


def sdf_color(color):
    return f'<ambient>{color}</ambient><diffuse>{color}</diffuse><specular>0.08 0.08 0.08 1</specular>'

def sdf_material(mat):
    return simple_sdf_material(PALETTE[mat])

def simple_sdf_material(rgb):
    """Material fallback for the original OBJ meshes; it needs no renderer texture support."""
    color=' '.join(f'{v:.3f}' for v in rgb)+' 1'
    return f'<material><ambient>{color}</ambient><diffuse>{color}</diffuse><specular>0.08 0.08 0.08 1</specular></material>'

def _obj_material_groups(obj_path):
    """Split an existing OBJ by its MTL material without changing any vertices/faces."""
    lines=obj_path.read_text().splitlines()
    vertices=[line for line in lines if line.startswith(('v ','vt ','vn '))]
    groups={}; active=None
    for line in lines:
        if line.startswith('usemtl '):
            active=line.split(maxsplit=1)[1].strip(); groups.setdefault(active,[])
        elif line.startswith(('f ','l ')) and active:
            groups[active].append(line)
    colors={}
    mtl_path=obj_path.with_suffix('.mtl')
    if mtl_path.exists():
        active_mtl=None
        for line in mtl_path.read_text().splitlines():
            fields=line.split()
            if len(fields)==2 and fields[0]=='newmtl':
                active_mtl=fields[1]
            elif len(fields)==4 and fields[0]=='Kd' and active_mtl:
                try: colors[active_mtl]=tuple(float(v) for v in fields[1:])
                except ValueError: pass
    generated={}
    for mat,faces in groups.items():
        if mat not in PALETTE and mat not in colors:
            continue
        out=obj_path.with_name(f'{obj_path.stem}_{mat}{obj_path.suffix}')
        out.write_text('\n'.join(vertices+faces)+'\n')
        generated[mat]=(out,colors.get(mat,PALETTE.get(mat,(.48,.46,.41))))
    return generated

def apply_original_layout_materials(sdf_path=None):
    """Add explicit solid SDF materials to the original scene's OBJ visuals.

    The old scene's MTL files contain material colors, but Gazebo may display
    imported OBJ visuals with its default material. Splitting by MTL group and
    assigning SDF colors preserves the original object geometry and layout.
    """
    import re
    sdf_path=sdf_path or (ROOT/'earthquake_landslide_world.sdf')
    text=sdf_path.read_text()
    changed=0
    # Split every reusable structure mesh, including intact houses used only in
    # the landslide-only scenario, so generated variants also get SDF colors.
    for obj_path in MESH.glob('*.obj'):
        _obj_material_groups(obj_path)
    visual_re=re.compile(r'(<visual\b[^>]*>)(.*?)(</visual>)',re.S)
    uri_re=re.compile(r'<uri>model://earthquake_landslide_assets/meshes/([^<]+\.obj)</uri>')
    def replace_visual(match):
        nonlocal changed
        opening,body,closing=match.groups()
        if '<material>' in body:
            return match.group(0)
        uri_match=uri_re.search(body)
        if not uri_match:
            return match.group(0)
        obj_name=uri_match.group(1)
        obj_path=MESH/obj_name
        if not obj_path.exists():
            return match.group(0)
        groups=_obj_material_groups(obj_path)
        if not groups:
            return match.group(0)
        base_name=re.search(r'\bname="([^"]+)"',opening)
        visual_base=base_name.group(1) if base_name else 'visual'
        pieces=[]
        for mat,(split_path,rgb) in groups.items():
            piece_body=body.replace(uri_match.group(0),uri_match.group(0).replace(obj_name,split_path.name),1)
            if base_name:
                piece_opening=opening.replace(base_name.group(0),f'name="{visual_base}_{mat}"',1)
            else:
                piece_opening=opening[:-1]+f' name="{visual_base}_{mat}">'
            piece_body=piece_body.replace('</geometry>',f'</geometry>{simple_sdf_material(rgb)}',1)
            pieces.append(piece_opening+piece_body+closing)
        changed+=1
        return ''.join(pieces)
    text=visual_re.sub(replace_visual,text)
    sdf_path.write_text(text)
    return changed

def box_model(name,x,y,z,sx,sy,sz,color, yaw=0, collision=True):
    coll=f'<collision name="collision"><geometry><box><size>{sx} {sy} {sz}</size></box></geometry></collision>' if collision else ''
    return f'''<model name="{name}"><static>true</static><pose>{x:.2f} {y:.2f} {z:.2f} 0 0 {yaw:.3f}</pose><link name="body"><visual name="visual"><geometry><box><size>{sx} {sy} {sz}</size></box></geometry><material>{sdf_color(color)}</material></visual>{coll}</link></model>'''

def mesh_model(name,uri,x,y,z,yaw,collisions):
    cs=''.join(f'<collision name="collision_{i}"><pose>{cx} {cy} {cz} 0 0 {cyaw}</pose><geometry><box><size>{sx} {sy} {sz}</size></box></geometry></collision>' for i,(cx,cy,cz,sx,sy,sz,cyaw) in enumerate(collisions))
    stems=uri if isinstance(uri,(list,tuple)) else [uri]
    visuals=[]
    for stem in stems:
        mats=sorted({p.stem[len(stem)+1:] for p in MESH.glob(f'{stem}_*.obj')})
        if not mats: mats=['']
        for mat in mats:
            asset=f'{stem}_{mat}' if mat else stem
            material=sdf_material(mat) if mat in PALETTE else ''
            visuals.append(f'<visual name="visual_{asset}"><geometry><mesh><uri>model://earthquake_landslide_assets/meshes/{asset}.obj</uri></mesh></geometry>{material}</visual>')
    return f'''<model name="{name}"><static>true</static><pose>{x:.2f} {y:.2f} {z:.2f} 0 0 {yaw:.3f}</pose><link name="body">{''.join(visuals)}{cs}</link></model>'''

def terrain_feature_z(x,y): return height(x,y,'combined')

def make_world():
    parts=[]
    parts.append('''<?xml version="1.0"?>
<sdf version="1.9"><world name="earthquake_landslide_world">
<gravity>0 0 -9.81</gravity><magnetic_field>6e-06 2.3e-05 -4.2e-05</magnetic_field><atmosphere type="adiabatic"/>
<physics name="harmonic_physics" type="ode"><max_step_size>0.004</max_step_size><real_time_factor>1</real_time_factor><real_time_update_rate>250</real_time_update_rate></physics>
<scene><ambient>0.52 0.55 0.58 1</ambient><background>0.57 0.68 0.76 1</background><shadows>true</shadows><grid>false</grid><fog><type>linear</type><color>0.68 0.74 0.78 1</color><start>95</start><end>260</end></fog></scene>
<spherical_coordinates><surface_model>EARTH_WGS84</surface_model><world_frame_orientation>ENU</world_frame_orientation><latitude_deg>27.9881</latitude_deg><longitude_deg>86.9250</longitude_deg><elevation>1450</elevation></spherical_coordinates>
<light name="sun" type="directional"><pose>0 0 100 0 0 0</pose><cast_shadows>true</cast_shadows><intensity>1.05</intensity><direction>-0.38 0.24 -0.89</direction><diffuse>0.92 0.90 0.82 1</diffuse><specular>0.25 0.25 0.25 1</specular><attenuation><range>1000</range><constant>1</constant><linear>0</linear><quadratic>0</quadratic></attenuation></light>
<model name="terrain"><static>true</static><link name="landform"><visual name="visual"><geometry><heightmap><uri>model://earthquake_landslide_assets/meshes/terrain_combined.png</uri><size>180 150 50</size><pos>0 0 0</pos><texture><size>180</size><diffuse>model://earthquake_landslide_assets/materials/textures/terrain_albedo_combined.png</diffuse><normal>model://earthquake_landslide_assets/materials/textures/terrain_normal.png</normal></texture><sampling>1</sampling></heightmap></geometry></visual><collision name="collision"><geometry><heightmap><uri>model://earthquake_landslide_assets/meshes/terrain_combined.png</uri><size>180 150 50</size><pos>0 0 0</pos><sampling>1</sampling></heightmap></geometry></collision></link></model>
''')
    # Launch area and three pads all follow flattened heightmap (surface ~1.5m).
    parts.append(box_model('launch_apron',-70,-56,1.56,20,18,.12,'0.34 0.36 0.35 1'))
    for i,(x,y) in enumerate([(-75,-60),(-67,-60),(-75,-52)],1):
        parts.append(box_model(f'launch_pad_{i}',x,y,1.66,3.2,3.2,.08,'0.16 0.48 0.25 1'))
    # One curved, non-colliding water mesh follows the same channel as the terrain.
    parts.append('''<model name="river_surface"><static>true</static><link name="water"><visual name="visual"><geometry><mesh><uri>model://earthquake_landslide_assets/meshes/river_surface.obj</uri></mesh></geometry><material><ambient>0.08 0.28 0.38 1</ambient><diffuse>0.10 0.38 0.52 1</diffuse><specular>0.4 0.4 0.4 1</specular></material></visual></link></model>''')
    # Cracked winding road pieces in the settlement valley, leaving visible gaps.
    for i,(x,y,yaw) in enumerate([(-42,-35,.55),(-34,-23,.55),(-26,-11,.55),(-19,2,.55),(-12,15,.55),(-5,28,.55),
                                  (-48,8,-.12),(-34,8,-.12),(-20,8,-.12)]):
        z=height(x,y,'combined')+.18
        parts.append(box_model(f'road_segment_{i}',x,y,z,13.0,3.6,.18,'0.20 0.22 0.23 1',yaw))
    # Ruined settlement north/west of water, scaled for the 180 x 150 m terrain.
    sites=[(-52,20,0),(-43,-8,.12),(-32,30,-.2),(-18,-27,.3),(4,27,-.18),(18,-18,.1)]
    for i,(x,y,yaw) in enumerate(sites):
        z=height(x,y,'combined')
        if i in (0,2,4):
            parts.append(mesh_model(f'earthquake_apartment_{i}','collapsed_apartment',x,y,z,yaw,
                   [(-0.5,0,2.1,10.5,8.5,4.2,0),(-.5,0,7.5,9.5,8.0,3.5,0)]))
        else:
            parts.append(mesh_model(f'earthquake_house_{i}','buried_village_house',x,y,z,yaw,
                   [(0,0,1.2,7.5,6.5,2.4,0),(-.4,0,3.0,5.0,5.5,1.5,0)]))
    # Distinct bridge crossing at central river, with two approach piles.
    bx=-4; by=0; bz=height(bx,by,'combined')+1.1
    parts.append(mesh_model('earthquake_damaged_bridge','damaged_bridge',bx,by,bz,.43,
                            [(-8,0,4,13,6.5,1.1,0),(8,0,4,11,6.5,1.1,0),(-7,0,1.8,1.3,1.3,5.8,0),(7,0,1.8,1.3,1.3,5.8,0)]))
    # Seeded deterministic boulders and rubble piles along scar runout and settlement.
    rng=random.Random(505)
    for i in range(24):
        x=rng.uniform(5,67); y=rng.uniform(-40,45)
        if abs(x-river_x(y))<13: continue
        z=height(x,y,'combined')+rng.uniform(.8,1.8); r=rng.uniform(1.0,3.3)
        parts.append(f'''<model name="landslide_boulder_{i:02d}"><static>true</static><pose>{x:.2f} {y:.2f} {z:.2f} 0 0 {rng.uniform(-3,3):.3f}</pose><link name="body"><visual name="visual"><geometry><mesh><uri>model://earthquake_landslide_assets/meshes/irregular_boulder.obj</uri><scale>{r:.2f} {r*.88:.2f} {r*.74:.2f}</scale></mesh></geometry>{sdf_material('stone')}</visual><collision name="collision"><geometry><sphere><radius>{r*.78:.2f}</radius></sphere></geometry></collision></link></model>''')
    for i,(x,y) in enumerate([(-48,15),(-38,-12),(-23,22),(8,-28),(29,15),(48,-4),(36,35)]):
        z=height(x,y,'combined')+.25
        parts.append(mesh_model(f'landslide_rubble_{i}',('rubble_cluster','rubble_beams'),x,y,z,i*.31,[(-1,0,.8,8,7,1.8,0),(2,1,1.5,4,4,2.6,.2)]))
    # Static dust cues above the active scar (visual-only; no particle system).
    for i,y in enumerate((-18,2,22)):
        x=63+.28*y
        z=height(x,y,'combined')+5.0
        parts.append(f'''<model name="landslide_dust_{i}"><static>true</static><pose>{x:.2f} {y:.2f} {z:.2f} 0 0 0</pose><link name="dust"><visual name="dust_cloud"><geometry><sphere><radius>{3.5+i*.4}</radius></sphere></geometry><material><ambient>0.62 0.55 0.46 1</ambient><diffuse>0.62 0.55 0.46 1</diffuse></material><transparency>0.52</transparency></visual></link></model>''')
    # Restricted-access fissures: dark visual slots with edge collision lips; terrain remains authoritative.
    for i,(x,y,yaw) in enumerate([(8,18,.8),(23,5,.7),(40,-18,.9),(-28,2,1.3)]):
        z=height(x,y,'combined')+.05
        parts.append(box_model(f'earthquake_crevice_{i}',x,y,z,10,.45,.08,'0.08 0.09 0.09 1',yaw,collision=False))
    # Colorful sparse forest silhouettes on outer slopes: trunks and conical canopies.
    rng=random.Random(733)
    for i in range(42):
        x=rng.choice([rng.uniform(-82,-67),rng.uniform(68,82),rng.uniform(-81,81)])
        y=rng.uniform(-64,64)
        if math.sqrt((x+70)**2+(y+56)**2)<20 or abs(x-(-8-.47*y))<15: continue
        z=height(x,y,'combined')
        h=rng.uniform(3.5,7.0)
        parts.append(f'''<model name="tree_{i:02d}"><static>true</static><pose>{x:.2f} {y:.2f} {z:.2f} 0 0 {rng.random()*6.28:.2f}</pose><link name="trunk"><visual name="trunk_visual"><pose>0 0 {h/2:.2f} 0 0 0</pose><geometry><cylinder><radius>.22</radius><length>{h:.2f}</length></cylinder></geometry><material>{sdf_color('0.29 0.20 0.12 1')}</material></visual><collision name="trunk_collision"><pose>0 0 {h/2:.2f} 0 0 0</pose><geometry><cylinder><radius>.22</radius><length>{h:.2f}</length></cylinder></geometry></collision></link><link name="canopy"><pose>0 0 {h*.78:.2f} 0 0 0</pose><visual name="canopy_visual"><geometry><sphere><radius>{h*.34:.2f}</radius></sphere></geometry><material>{sdf_color(rng.choice(['0.14 0.34 0.18 1','0.20 0.42 0.22 1','0.27 0.43 0.20 1']))}</material></visual><collision name="canopy_collision"><geometry><sphere><radius>{h*.31:.2f}</radius></sphere></geometry></collision></link></model>''')
    # Fixed inspection and fire/victim markers are separate models; perception sensors are external.
    for i,(x,y,kind) in enumerate([(-46,10,'victim'),(-28,24,'victim'),(16,-25,'victim'),(33,13,'fire'),(45,-12,'fire'),(-5,35,'fire')]):
        z=height(x,y,'combined')+.45
        if kind=='victim':
            parts.append(f'''<model name="incident_victim_{i}"><static>true</static><pose>{x} {y} {z} 0 0 0</pose><link name="body"><visual name="visual"><geometry><cylinder><radius>.35</radius><length>.8</length></cylinder></geometry><material>{sdf_color('0.05 0.32 0.88 1')}</material></visual><collision name="collision"><geometry><cylinder><radius>.35</radius><length>.8</length></cylinder></geometry></collision></link></model>''')
        else:
            parts.append(f'''<model name="incident_fire_{i}"><static>true</static><pose>{x} {y} {z} 0 0 0</pose><link name="marker"><visual name="flame_visual"><geometry><cone><radius>1.1</radius><length>2.8</length></cone></geometry><material>{sdf_color('1.0 0.24 0.025 1')}</material></visual></link></model>''')
            parts.append(f'''<model name="incident_smoke_{i}"><static>true</static><pose>{x+1.2} {y} {z+3.2} 0 0 0</pose><link name="plume"><visual name="smoke_visual"><geometry><sphere><radius>1.5</radius></sphere></geometry><material>{sdf_color('0.29 0.30 0.30 0.62')}</material></visual></link></model>''')
    parts.append('</world></sdf>')
    (ROOT/'earthquake_landslide_world.sdf').write_text('\n'.join(parts)+'\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=['combined','earthquake','landslide'],default=None); ap.add_argument('--seed',type=int,default=2026); ap.add_argument('--output',type=Path,default=None); args=ap.parse_args()
    ASSET.mkdir(exist_ok=True,parents=True); MESH.mkdir(exist_ok=True,parents=True); TEX.mkdir(exist_ok=True,parents=True)
    if args.mode is None:
        changed=apply_original_layout_materials()
        print(f'Applied explicit SDF colors to {changed} mesh visuals; terrain, object poses, and collisions were preserved.')
        return
    source=ROOT/'earthquake_landslide_world.sdf'; tree=ET.parse(source); root=tree.getroot(); world=root.find('world')
    # Select terrain; preserve common test area. Deterministic incident placements shift per seed.
    hm=world.find(".//visual/geometry/heightmap/uri")
    hm.text=f'model://earthquake_landslide_assets/meshes/terrain_{args.mode}.png'
    hm2=world.find(".//collision/geometry/heightmap/uri")
    if hm2 is not None: hm2.text=hm.text
    diffuse=world.find(".//visual/geometry/heightmap/texture/diffuse")
    if diffuse is not None:
        diffuse.text=f'model://earthquake_landslide_assets/materials/textures/terrain_albedo_{args.mode}.png'
    for model in list(world.findall('model')):
        n=model.get('name','')
        if args.mode=='earthquake' and n.startswith('landslide_'): world.remove(model)
        if args.mode=='landslide' and n.startswith('earthquake_crevice_'): world.remove(model)
        if args.mode=='landslide' and n.startswith('incident_'):
            # keep incident markers for perception trials, but shift deterministically below
            pass
    rng=random.Random(args.seed)
    if args.mode=='landslide':
        # Keep the settlement present, but substitute intact shells so this mode
        # isolates slide terrain and debris from earthquake building collapse.
        for model in list(world.findall('model')):
            name=model.get('name','')
            if name.startswith(('earthquake_apartment_','earthquake_house_')):
                pose=[float(v) for v in model.find('pose').text.split()]
                replacement=ET.fromstring(mesh_model(
                    'settlement_intact_'+name.removeprefix('earthquake_'),
                    'intact_village_house',pose[0],pose[1],pose[2],pose[5],
                    [(0,0,1.4,7.2,6.2,2.8,0)]))
                world.remove(model); world.append(replacement)
    incident_offsets={}
    for model in world.findall('model'):
        name=model.get('name','')
        if name.startswith(('incident_victim_','incident_fire_','incident_smoke_')):
            pose=model.find('pose')
            vals=[float(v) for v in pose.text.split()]
            _, suffix=name.rsplit('_',1)
            key=suffix
            if key not in incident_offsets:
                incident_offsets[key]=(rng.uniform(-4,4),rng.uniform(-4,4))
            dx,dy=incident_offsets[key]
            vals[0]+=dx; vals[1]+=dy
            pose.text=' '.join(f'{v:.3f}' for v in vals)
    out=args.output or ROOT/f'{args.mode}_seed_{args.seed}.sdf'
    tree.write(out,encoding='utf-8',xml_declaration=True)
    manifest={'world':str(out.name),'mode':args.mode,'seed':args.seed,'terrain':f'terrain_{args.mode}.png','texture':f'terrain_albedo_{args.mode}.png','incident_markers':'deterministically jittered +/- 4 m','drones':'externally spawned at launch pads'}
    out.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__': main()
