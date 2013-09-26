import sublime
# from sublime_plugin import WindowCommand
from sublime_plugin import TextCommand, EventListener, WindowCommand
from subprocess import Popen, PIPE, STDOUT
from queue import Queue
from threading import Thread, Timer
import os
import json
import re


# What if: 
# new file: if in the files list, then just update
# if not in it, re-initialize? How can you? You can't really clean up nicely

# http://www.eladyarkoni.com/2012/09/sublime-text-auto-complete-plugin.html

BIN_PATH = os.path.join(os.path.dirname(__file__), 'bin')
TSS_PATH = os.path.join(BIN_PATH, 'tss.js')
TSC_PATH = os.path.join(BIN_PATH, 'tsc.js')

class TypescriptProjectManager(object):

    def __init__(self):
        self.services = {}

    # returns an initializes a project given a certain view
    def service(self, view):
        if not view: return None

        window_id = str(view.window().id())
        if window_id in self.services:
            return self.services[window_id]

        service = TypescriptToolService(window_id)

        file = project_main(view)
        if file:
            project_file = view.window().project_file_name()
            file_path = os.path.join(os.path.dirname(project_file), file)
            # TODO save that file_path somewhere for building
            service.initialize(file_path)

        self.services[window_id] = service
        return service

    def service_by_window(self, window):
        window_id = str(window.id())
        if window_id in self.services:
            return self.services[window_id]

        service = TypescriptToolService(window_id)
        return service

    def unload(self):
        for service in self.services.values():
            service.destroy()
        self.services = {}




 


projects = TypescriptProjectManager()

class TypescriptToolService(object):

    ERRORS_DELAY = 0.3
    
    def __init__(self, service_id):
        # print("TypescriptToolService()", service_id)
        self.service_id = service_id
        self.errors = []
        self.loaded = False
        self.completions = []
        self.tools = None
        self.tools_sync = None
        self.errors_timer = None
        self.completions_valid = False
        self.delegate = None

    def is_initialized(self):
        return self.tools != None

    def initialize(self, root_file_path):
        # can only initialize once
        print("initialize", self.service_id, root_file_path)
        self.loaded = False        

        # kwargs = {}
        # self.tools = ToolsBridge(self.service_id)
        # self.tools.connect(root_file_path, self.on_loaded)

        self.tools_sync = ToolsSyncBridge(self.service_id)
        self.tools_sync.connect(root_file_path, self.on_loaded)


    # Only allow you to start once for now? 
    def start(self, file_path):
        return
        self.initialize(file_path)

    def set_build_errors(self, errors): 
        self.errors = errors
        if (self.delegate):
            self.delegate.on_typescript_errors(self.errors)


    def on_loaded(self, message):
        # print("on_loaded", self.service_id)
        self.loaded = True
        # self.check_errors()
        if (self.delegate):
            self.delegate.on_typescript_loaded()

    def check_errors_delay(self): 
        print("check_errors_delay")
        if self.errors_timer: 
            self.errors_timer.cancel()
        self.errors_timer = Timer(self.ERRORS_DELAY, self.check_errors)
        self.errors_timer.start()

    def check_errors(self):
        return
        print("check_errors")
        self.tools.add('showErrors', self.on_errors)

    def on_errors(self, error_infos):
        self.errors = list(map(lambda e: Error(e), error_infos))
        if (self.delegate):
            self.delegate.on_typescript_errors(self.errors)

    def add_file(self, view):
        print("add_file", view.file_name())
        # don't check errors here?
        if (self.is_initialized()):
            if (self.loaded):
                self.update_file(view)

        else:
            self.initialize(view.file_name())

    # automatically runs checkerrors
    def update_file(self, view):
        if not view.file_name(): return
        
        content = view.substr(sublime.Region(0, view.size()))
        lines = content.split('\n')
        file_name = view.file_name().replace('\\','/')
        line_count = len(lines)
        print("update_file", file_name, view.size(), len(lines))        

        command = 'update nocheck {0} {1}\n{2}'.format(line_count, file_name, content)
        # self.tools.add(command, self.on_updated)
        self.on_updated(self.tools_sync.command(command))

    def invalidate_completions(self):
        self.completions = []
        self.completions_valid = False
        
    def on_updated(self, message): 
        # print("UPDATED", message)
        return

    def list_files(self):
        # self.tools.add('files', self.on_list_files)
        self.on_list_files(self.tools_sync.command('files'))
        
    def on_list_files(self, files):
        print("FILES", files)
        if self.delegate:
            self.delegate.on_typescript_files(files)

    def destroy(self):
        # self.tools.stop()
        self.tools_sync.stop()

    # line and pos start at 1, not 0!
    def load_completions(self, is_member, line, pos, file, on_completions):
        return
        member_out = str(is_member).lower()
        command = "completions {0} {1} {2} {3}".format(member_out, str(line), str(pos), file)
        service = self
        
        def on_data(data):
            if data and 'entries' in data:
                # print("COMPLETIONS", entries)
                completions = list(map(lambda c: Completion(c), data['entries']))
                service.completions = [c for c in completions if is_completion_valid(c)]
                service.completions_valid = True
                on_completions(service.completions)
            else:
                print("!!! Completions")

        self.tools.add(command, on_data)

    def load_completions_sync(self, is_member, line, pos, file):
        member_out = str(is_member).lower()
        command = "completions {0} {1} {2} {3}".format(member_out, str(line), str(pos), file)
        data = self.tools_sync.command(command)

        completions = []

        if data and 'entries' in data:
            # print("COMPLETIONS", entries)
            completions = list(map(lambda c: Completion(c), data['entries']))
            completions = [c for c in completions if is_completion_valid(c)]

        self.completions = completions
        return self.completions

    def load_completions_view(self, view, on_completions):
        pos = view.sel()[0].begin()
        (line, col) = view.rowcol(pos)
        is_member = True        
        self.load_completions(is_member, line+1, col+1, view.file_name(), on_completions)

    def load_completions_view_sync(self, view):
        pos = view.sel()[0].begin()
        (line, col) = view.rowcol(pos)
        is_member = True        
        completions = self.load_completions_sync(is_member, line+1, col+1, view.file_name())
        return completions







class ToolsSyncBridge(object):

    def __init__(self, service_id):
        self.service_id = service_id
        self.process = None

    def connect(self, root_file_path, on_loaded):
        kwargs = {}
        process = Popen(["/usr/local/bin/node", TSS_PATH, root_file_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
        self.process = process

        # initalizing. sends "loaded"
        line = tools_read(self.process.stdout)
        print("LOADED", line)
        on_loaded(line)

    def command(self, command):
        tools_write(self.process.stdin, command)
        data = tools_read(self.process.stdout)
        return data

    def stop(self):
        self.process.kill()


class ToolsBridge(object):
    
    def __init__(self, service_id):
        self.service_id = service_id
        self.process = None

    def connect(self, root_file_path, on_loaded):
        kwargs = {}
        process = Popen(["/usr/local/bin/node", TSS_PATH, root_file_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
        self.process = process

        self.writer = ToolsWriter(process.stdin, self.service_id)
        self.writer.start()

        self.reader = ToolsReader(process.stdout, self.service_id)
        self.reader.add(on_loaded) # need to consume the "loaded" response
        self.reader.start()

    def add(self, message, on_data):
        if not self.process: return
        self.writer.add(message)
        self.reader.add(on_data)
        # you want to do it synchronously, no?
        # hmm... 

    # def write(self, message):
    #     self.writer.add(message)

    # def read(self, on_data):
    #     self.reader.add(on_data)

    def stop(self):
        self.process.kill()
 

class ToolsWriter(Thread):

    def __init__(self, stdin, service_id):
        Thread.__init__(self)
        self.stdin = stdin        
        self.daemon = True
        self.service_id = service_id
        self.queue = Queue()

    def add(self, message):
        self.queue.put(message)

    def run(self):
        for command in iter(self.queue.get, None):
            tools_write(self.stdin, command)
        self.stdin.close()

class ToolsReader(Thread):

    # have an ARRAY of handlers, one should get called per line, or you throw an error

    def __init__(self, stdout, service_id):
        Thread.__init__(self)
        self.stdout = stdout
        self.daemon = True
        self.service_id = service_id
        self.line_handlers = Queue() 

    def add(self, handler):
        self.line_handlers.put(handler, False) # don't block

    def read_sync(self):
        return tools_read(self.stdout)

    def run(self):
        for data in iter(self.read_sync, b''):
            on_data = self.line_handlers.get(False) # don't block
            on_data(data)

        self.stdout.close()




def tools_write(stdin, command):
    print("TOOLS (write) {0} [{1}]".format(command.partition("\n")[0][:200], len(command)))
    stdin.write(bytes(command+'\n','UTF-8'))

def tools_read(stdout):
    line = stdout.readline().decode('UTF-8')
    print("TOOLS (read)", line.partition("\n")[0][:200])
    data = json.loads(line)
    return data




def render_errors(view, errors):
    file = view.file_name()
    # print("RENDER_ERRORS", len(errors), file)
    matching_errors = [e for e in errors if e.file == file]
    regions = list(map(lambda e: error_region(view, e), matching_errors))
    view.add_regions('typescript-error', regions, 'invalid', 'cross', sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE)

def render_error_status(view, errors):
    sel = view.sel()
    (line, col) = view.rowcol(sel[0].begin())
    line_error = find_error(errors, line, view.file_name())
    if line_error:
        view.set_status("typescript", line_error.text)    
    else:
        view.erase_status("typescript")


def error_region(view, error):
    a = view.text_point(error.start.line-1, error.start.character-1)
    b = view.text_point(error.end.line-1, error.end.character-1)
    return sublime.Region(a, b)

def find_error(errors, line, file):
    for error in errors:
        if error.file == file and (line+1 >= error.start.line and line+1 <= error.end.line):
            return error
    return None



# shows the currently indexed files (mostly for debugging, but you could use it to jump to ONLY typescript files if you wanted
class TypescriptShowFilesCommand(TextCommand):

    def run(self, edit):
        service = projects.service(self.view)
        service.delegate = self
        service.list_files()

    def on_typescript_files(self, files):
        # ignore the files added by tss.js
        print("FILES!!!")
        bin_path = os.path.join("sublime-typescript", "bin")
        self.files = [file for file in files if not bin_path in file]
        items = list(map(lambda f: [os.path.basename(f), os.path.dirname(f)], self.files))
        sublime.active_window().show_quick_panel(items, self.on_select_panel_item)

    def on_select_panel_item(self, index):
        if index < 0: return
        file = self.files[index]
        sublime.active_window().open_file(file)


# Starts typescript with the current view as the root file
# useful if you started with another file
class TypescriptStartCommand(TextCommand):
    
    def run(self, edit):
        projects.unload()
        service = projects.service(self.view)
        service.add_file(self.view)
        service.check_errors()


 
# AUTO COMPLETION
# This doesn't quite work right. It returns a bunch of extra completions it shouldn't
# instead, use autocomplete: true
# class TypescriptComplete(TextCommand):

#     def run(self, edit, characters):
#         print("------------------------------------")
#         print("TypescriptComplete")
#         print("------------------------------------")
#         for region in self.view.sel():
#             self.view.insert(edit, region.end(), characters)

#         # 1. it doesn't purge anything, like it normally does.. oh, that's probably why?
#         # it's not updated
        
#         service = projects.service(self.view)
#         service.update_file(self.view)
#         service.invalidate_completions()
#         service.load_completions_view(self.view, self.on_typescript_completions)

#         # I need to be able to call back FOR THAT SPECIFIC INSTANCE
#         # this sucks :)
#         # in objective-c I'd use a block, so use it!

#     def on_typescript_completions(self, completions): 
#         print("-----------------------------------")
#         print("")
#         print("")
#         self.view.run_command('hide_auto_complete')
#         self.view.run_command('auto_complete',{
#             'disable_auto_insert': True,
#             'api_completions_only': True,
#             'next_competion_if_showing': True
#         })

# When you SAVE, do something 


# class TypescriptBuildClick(TextCommand):
#     def run(self, edit):
#         print("GOGO CHILD", self.view)



class TypescriptBuild(WindowCommand):

    

    def __init__(self, window):
        WindowCommand.__init__(self, window)
        self.build_errors_by_file = {}
        self.build_errors = []

        # output.set_syntax_file("Packages/Syntax/Syntax.tmLanguage")
        # output.set_syntax_file(os.path.join(os.path.dirname(__file__), "TypescriptBuild.tmLanguage"))
        # output.run_command('append', {'characters': "Building " + ', '.join(files) + "\n"})


    def run(self):
        self.build_errors_by_file = {}
        self.build_errors = []

        view = self.window.active_view()
        if not view: 
            return

        # they should be relative to the project

        thread = Thread(target=lambda: self.build(view))
        thread.daemon = True
        thread.start()

    def build(self, view):

        window = self.window
        project_file = window.project_file_name()

        file = project_main(view)
        abs_file = relative_file_path(project_file, file)

        # print("Typescript Build:", abs_files)
        view.set_status("typescript", "TS BUILD [ " + file + " ]")

        kwargs = {}
        command = ["/usr/local/bin/node", TSC_PATH, "-m", "commonjs"] + [abs_file]
        process = Popen(command, stdin=PIPE, stdout=PIPE, stderr=STDOUT, **kwargs)
        (stdout, stderr) = process.communicate()

        lines = stdout.decode('UTF-8').split("\n")
        self.build_errors_by_file = {}

        extra_lines = []
        total_errors = 0
        last_error = None

        self.output_create()

        for line in lines:
            # print(line)
            error = self.parse_error(line)
            if error:
                total_errors += 1
                self.add_build_error(error)
                last_error = error
            elif line:
                # print("HI", line)
                # print("EXTRA LINE BABY", error, line)
                if last_error:
                    last_error.text += line + "\n"
                else:
                    extra_lines.append(line)
        
        
        
        if (len(self.build_errors_by_file) == 0) and (len(extra_lines) == 0):
            # output.run_command('append', {'characters': '[ OK ]'})
            # output.run_command('close', {})
            # print("Typescript Build: [OK]")
            # view.set_status("typescript", "BUILD OK")
            view.erase_status("typescript")
            self.output_close()
            
        else:
            self.output_open()

            view.set_status("typescript", "TS ({0}) ERRORS".format(total_errors))

            for line in extra_lines:
                self.output_append(line + "\n")
        
            for file, errors in self.build_errors_by_file.items():
                relative_path = os.path.relpath(file, os.path.dirname(project_file))
                self.output_append(" {0} \n".format(relative_path))
                for error in errors:
                    self.output_append("  Line {0}: {1}\n".format(error.start.line, error.text))
                self.output_append("\n")  

        service = projects.service_by_window(self.window)
        service.set_build_errors(self.build_errors)

        # render_errors()                  

    def add_build_error(self, error):
        if not error.file in self.build_errors_by_file:
            self.build_errors_by_file[error.file] = []
        self.build_errors_by_file[error.file].append(error)
        self.build_errors.append(error)

    def errors_for_file(self, file):
        if not file in self.build_errors_by_file:
            return []
        return self.build_errors_by_file[file]

    def parse_error(self, line):
        # return a string or an error?
        # if it is a string, just print it out
        # "/Users/seanhess/projects/angularjs-bootstrap/server/server.ts(10,10): error TS1005: '=' expected."
        match = re.match('^(.+)\((\d+),(\d+)\): error (\w+): (.+)$', line)
        if not match: return None

        file = match.group(1)
        line = int(match.group(2))
        col = int(match.group(3))
        text = match.group(5)
        error = BuildError(file, line, col, text)

        return error

    def output_create(self):
        # ??? How do you erase one?
        self.output = self.window.create_output_panel('typescript_build')
        self.output.settings().set("color_scheme", "Packages/sublime-typescript/TypescriptBuild.tmTheme")         
        self.output.set_syntax_file("Packages/sublime-typescript/TypescriptBuild.tmLanguage")

    def output_open(self):
        self.window.run_command("show_panel", {"panel": "output.typescript_build"}) 
        
    def output_close(self):
        self.window.run_command("hide_panel", {"panel": "output.typescript_build"})        

    def output_append(self, characters):
        self.output.run_command('append', {'characters': characters})


class TypescriptEventListener(EventListener):

    def __init__(self):
        self.view_modified_time = 0
        self.timer = None
        self.completions_delay_done = False

    # called whenever a veiw is focused
    def on_activated_async(self,view): 
        # print("on_activated_async", view.file_name())
        if not is_typescript(view): 
            self.current_view = None
            return
        
        self.current_view = view
        service = projects.service(view)
        service.delegate = self
        
        render_errors(view, service.errors)

        # you don't need to update the file here, it's already been loaded
        # service.add_file(view)
        # service.check_errors()

        # print(" - service", service.service_id)
        
        # if it is a typescript file, and we aren't loaded, run LOAD synchronously. Just burn through it fast

    def on_clone_async(self,view):
        return
        # print("on_clone_async")

    def on_typescript_files(self, files):
        return

    def init_view(self,view):
        return
        # print("init_view")

    def on_load_async(self, view):
        return
        # print("on_load_async")


    def on_typescript_loaded(self):
        return

    # # called on each character sent
    def on_modified_async(self, view):
        if not is_typescript(view): return
        if not view.file_name(): return

        # self.mark_view_dirty(view)

        # immediately update
        # print("on modified async", view.file_name(), view)
        service = projects.service(view)
        service.delegate = self
        # service.update_file(view)
        # service.check_errors_delay()
        service.invalidate_completions()
        self.completions_delay_done = False

        # immediately check completions too?
        # service.load_completions_view(self.current_view)
        

    def on_typescript_errors(self, errors):
        if self.current_view:
            render_errors(self.current_view, errors)
        
    # # called a lot when selecting, AND each character
    def on_selection_modified_async(self, view):
        if not is_typescript(view): return

        service = projects.service(view)
        service.delegate = self        
        render_error_status(view, service.errors)

    # def on_post_save_async(self,view):
    #     print("on_post_save_async")



    # debouce this, so it waits until they STOP typing to do it

    def on_query_completions(self, view, prefix, locations):
        print("on_query_completions")
        if not is_typescript(view): return

        self.current_view = view

        print("on_query_completions")
        service = projects.service(view)
        service.delegate = self

        if self.completions_delay_done:
            service.update_file(view)
            completions = service.load_completions_view_sync(view)
            sublime_completions = list(map(completion_item, completions))
            return (sublime_completions, sublime.INHIBIT_WORD_COMPLETIONS)

        else:
            self.completions_delay()
            return ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)



        # service.update_file(view)
        # completions = service.load_completions_view_sync(view)
        # sublime_completions = list(map(completion_item, completions))
        # return (sublime_completions, sublime.INHIBIT_WORD_COMPLETIONS)
        
        # if completions is 0! Not the right way to do this!
        # should be if... if... we haven't updated them
        # if service.completions_valid:
        #     print(" - render " + str(len(service.completions)))
        #     completions = list(map(completion_item, service.completions))
        #     return (completions)

        # else:
        #     print(" - load")
        #     self.current_view = view
        #     service.completions_valid = False
        #     service.update_file(view)
        #     service.load_completions_view(view, self.on_typescript_completions)
        #     return ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def completions_delay(self): 
        self.completions_delay_done = False
        if self.timer: 
            self.timer.cancel()
        self.timer = Timer(0.25, self.force_completions)
        self.timer.start()

    def force_completions(self):
        self.completions_delay_done = True
        # self.current_view.run_command('hide_auto_complete')
        self.current_view.run_command('auto_complete',{
            'disable_auto_insert': True,
            'api_completions_only': True,
            'next_competion_if_showing': True
        })

    def on_typescript_completions(self, completions):
        self.force_completions()

    def on_post_save_async(self, view):
        if not is_typescript(view): return

        print("SAVE", view, project_main(view), view.file_name())
        sublime.active_window().run_command("typescript_build", {})
                    
    # def on_query_context(self, view, key, operator, operand, match_all):
    #     if key == "typescript":
    #         view = sublime.active_window().active_view()
    #         return is_ts(view)        
 

def is_typescript(view):
    if view is None:
        view = sublime.active_window().active_view()
    return 'source.ts' in view.scope_name(0)

def plugin_loaded():
    #settings = sublime.load_settings('typescript.sublime-settings')
    #print("TS Loaded", settings)
    print("Typescript: Loaded")

def completion_item(completion):
    key = completion_key(completion)
    value = completion_value(completion)
    return (key, value)


def completion_key(completion):
    type = completion.type
    if not is_completion_function(completion):
        type = ":" + type
    return completion.name + type

# turn this into a snippet!
def completion_value(completion):

    # (ext: string, fn: Function): ExpressApplication    
    if not is_completion_function(completion):
        return completion.name

    # the regular expressions were slow
    match = re.match('\((.*)\)\:', completion.type)
    if not match: 
        return completion.name

    # make a snippeter target thing for each parameter
    parameters = match.group(1).split(',')
    snippets = []
    for param in parameters:
        snippets.append("${" + str(len(snippets)+1) + ":" + param + "}")

    snippet = completion.name + "(" + ", ".join(snippets) + ")"
    return snippet


def is_completion_valid(completion):
    return completion.type != None

def is_completion_function(completion):
    return (completion.kind == 'method' or completion.kind == 'function')

def relative_file_path(project_file, file):
    if not file:
        return None
    return os.path.join(os.path.dirname(project_file), file)

def relative_file_paths(window, files):
    project_file = window.project_file_name()
    abs_files = list(map(lambda f: relative_file_path(project_file, f), files))
    return abs_files

def project_main(view):
    return view.window().project_data()["typescript_main"]


class Completion(object):
    def __init__(self, dict):
        self.name = dict['name']
        self.type = dict['type']
        self.kind = dict['kind']
        self.full_symbol_name = dict['fullSymbolName']
        self.kind_modifiers = dict['kindModifiers']
        self.doc_comment = dict['docComment']

class Error(object):
    def __init__(self, dict):
        self.file = dict['file']
        self.text = dict['text']

        self.start = ErrorPosition(dict['start'])
        self.end = ErrorPosition(dict['end'])
        
        self.phase = dict['phase']
        self.category = dict['category']

class BuildError(object):
    def __init__(self, file, line, col, text):
        self.file = file
        self.text = text

        self.start = ErrorPosition({'line': line, 'character': col})
        self.end = ErrorPosition({'line': line, 'character': col+3})
        
        self.phase = None
        self.category = None

class ErrorPosition(object):
    def __init__(self, dict):
        self.line = dict['line']
        self.character = dict['character']    
