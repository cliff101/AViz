[app]

title = AViz
project_dir = .
input_file = main.py
icon =

[python]

# Android: no scipy/pyqtgraph (native crashes); numpy + Qt only. Desktop uses requirements.txt.
packages = numpy

android_packages = buildozer==1.5.0,cython==0.29.33

[qt]

modules = Core,Gui,Widgets,Multimedia
plugins =

[android]

# Leave empty — pyside6-android-deploy auto-detects Android plugins from Qt modules.
plugins =

[buildozer]

mode = debug
arch = aarch64
# ndk_path / sdk_path set in CI
