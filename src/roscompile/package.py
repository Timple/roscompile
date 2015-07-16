import os
import os.path
import collections
from roscompile.launch import Launch 
from roscompile.source import Source
from roscompile.setup_py import SetupPy
from roscompile.package_xml import PackageXML
from roscompile.plugin_xml import PluginXML

SRC_EXTS = ['.py', '.cpp', '.h']
CONFIG_EXTS = ['.yaml', '.rviz']
DATA_EXTS = ['.dae', '.jpg', '.stl', '.png']
MODEL_EXTS = ['.urdf', '.xacro', '.srdf']

EXTS = {'source': SRC_EXTS, 'config': CONFIG_EXTS, 'data': DATA_EXTS, 'model': MODEL_EXTS}
BASIC = ['package.xml', 'CMakeLists.txt']
SIMPLE = ['.launch', '.msg', '.srv', '.action', '.cfg']
PLUGIN_CONFIG = 'plugins'
EXTRA = 'Extra!'

def match(ext):
    for name, exts in EXTS.iteritems():
        if ext in exts:
            return name
    return None

class Package:
    def __init__(self, root):
        self.root = root
        self.name = os.path.split(os.path.abspath(root))[-1]
        self.manifest = PackageXML(self.root + '/package.xml')
        self.files = self.sort_files()
        self.sources = [Source(source) for source in self.files['source']]

    def sort_files(self, print_extras=False):
        data = collections.defaultdict(list)
        
        plugins = self.manifest.get_plugin_xmls()
        
        for root,dirs,files in os.walk(self.root):
            if '.git' in root or '.svn' in root:
                continue
            for fn in files:
                ext = os.path.splitext(fn)[-1]
                full = '%s/%s'%(root, fn)
                if fn[-1]=='~':
                    continue
                ext_match = match(ext)

                if ext_match:
                    data[ext_match].append(full)
                elif ext in SIMPLE:
                    name = ext[1:]
                    data[name].append(full)
                elif fn in BASIC:
                    data[None].append(full)
                else:
                    found = False
                    for tipo, pfilename in plugins:
                        if os.path.samefile(pfilename, full):
                            data[PLUGIN_CONFIG].append( (pfilename, tipo) )
                            found = True
                            break
                    if found:
                        continue        
                    data[EXTRA].append(full)
        if print_extras and len(data[EXTRA])>0:
            for fn in data[EXTRA]:
                print '    ', fn

        return data

    def get_build_dependencies(self):
        packages = set()
        for source in self.sources:
            packages.update(source.get_dependencies())
        if self.name in packages:
            packages.remove(self.name)            
        return sorted(list(packages))

    def get_run_dependencies(self):
        packages = set()
        for launch in self.files['launch']:
            x = Launch(launch)
            packages.update(x.get_dependencies())
        if self.name in packages:
            packages.remove(self.name)
        return sorted(list(packages))

    def get_dependencies(self, build=True):
        if build:
            return self.get_build_dependencies()
        else:
            return self.get_run_dependencies()

    def update_manifest(self):
        for build in [True, False]:
            dependencies = self.get_dependencies(build)
            if build:
                self.manifest.add_packages(dependencies, build)
            self.manifest.add_packages(dependencies, False)

        self.manifest.output()
        
    def generate_setup(self):
        sources = [src for src in self.sources if src.python and 'setup.py' not in src.fn]
        if len(sources)==0:
            return
            
        setup = SetupPy(self.name, self.root, sources)

        if setup.valid:
            print "    Writing setup.py"
            setup.write()

        return
        
    def check_plugins(self):
        plugins = []
        for source in self.sources:
            plugins += source.get_plugins()
            
        configs = {}
        for filename, tipo in self.files[PLUGIN_CONFIG]:
            configs[tipo] = PluginXML(filename)
            
        pattern = '%s::%s'    
        for pkg1, name1, pkg2, name2 in plugins:
            if pkg2 not in configs:
                configs[pkg2] = PluginXML( self.root + '/plugins.xml')
                self.manifest.add_plugin_export('plugins.xml', pkg2)
            configs[pkg2].insert_if_needed(pattern%(pkg1, name1), pattern%(pkg2, name2))

        for config in configs.values():
            config.write()
        self.manifest.output()    
        
    def get_people(self):
        people = {}
        people['maintainers'] = self.manifest.get_people('maintainer')
        people['authors'] = self.manifest.get_people('author')
        return people

    def update_people(self, people, replace={}):
        self.manifest.update_people('maintainer', people, replace)
        self.manifest.update_people('author', people, replace)

def get_packages(root_fn='.'):
    packages = []
    for root,dirs,files in os.walk(root_fn):
        if '.git' in root:
            continue
        if 'package.xml' in files:
            packages.append(Package(root))
    return packages
