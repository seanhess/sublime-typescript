import sublime
# from sublime_plugin import WindowCommand
from sublime_plugin import TextCommand
from sublime_plugin import EventListener
from subprocess import Popen, PIPE
from queue import Queue
from threading import Thread, Timer
import os
import json
import re


# What if: 
# new file: if in the files list, then just update
# if not in it, re-initialize? How can you? You can't really clean up nicely

# http://www.eladyarkoni.com/2012/09/sublime-text-auto-complete-plugin.html

TSS_PATH = os.path.join(os.path.dirname(__file__),'bin', 'tss.js')

class TypescriptProjectManager(object):

    def __init__(self):
        self.services = {}

    # returns an initializes a project given a certain view
    def service(self, view):
        window_id = str(view.window().id())
        if window_id in self.services:
            return self.services[window_id]

        service = TypescriptToolService(window_id)

        file = view.settings().get("typescript_root")
        if file:
            project_file = view.window().project_file_name()
            file_path = os.path.join(os.path.dirname(project_file), file)
            # TODO save that file_path somewhere for building
            service.initialize(file_path)

        self.services[window_id] = service
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
        self.errors_timer = None

    def is_initialized(self):
        return self.tools != None

    def initialize(self, root_file_path):
        # can only initialize once
        print("initialize", self.service_id, root_file_path)
        self.loaded = False        

        # kwargs = {}
        self.tools = ToolsBridge(self.service_id)
        self.tools.connect(root_file_path, self.on_loaded)


    # Only allow you to start once for now? 
    def start(self, file_path):
        return
        self.initialize(file_path)


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
        
        content = view.substr(sublime.Region(0, view.size()))
        lines = content.split('\n')
        file_name = view.file_name().replace('\\','/')
        line_count = len(lines)
        print("update_file", file_name, view.size(), len(lines))        

        command = 'update nocheck {0} {1}\n{2}'.format(line_count, file_name, content)
        self.tools.add(command, self.on_updated)

    def invalidate_completions(self):
        self.completions = []
        
    def on_updated(self, message): 
        # print("UPDATED", message)
        return

    def list_files(self):
        self.tools.add('files', self.on_list_files)
        
    def on_list_files(self, files):
        print("FILES", files)
        if self.delegate:
            self.delegate.on_typescript_files(files)

    def destroy(self):
        self.tools.stop()

    # line and pos start at 1, not 0!
    def load_completions(self, is_member, line, pos, file, on_completions):
        member_out = str(is_member).lower()
        command = "completions {0} {1} {2} {3}".format(member_out, str(line), str(pos), file)
        service = self
        
        def on_data(data):
            if data and 'entries' in data:
                # print("COMPLETIONS", entries)
                completions = list(map(lambda c: Completion(c), data['entries']))
                service.completions = [c for c in completions if is_completion_valid(c)]
                on_completions(service.completions)
            else:
                print("!!! Completions")

        self.tools.add(command, on_data)


    def load_completions_view(self, view, on_completions):
        pos = view.sel()[0].begin()
        (line, col) = view.rowcol(pos)
        is_member = True        
        self.load_completions(is_member, line+1, col+1, view.file_name(), on_completions)












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

    def write_sync(self, command):
        print("TOOLS-{0} (write) {1} [{2}]".format(self.service_id, command.partition("\n")[0][:200], len(command)))
        self.stdin.write(bytes(command+'\n','UTF-8'))

    def run(self):
        for command in iter(self.queue.get, None):
            self.write_sync(command)
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
        line = self.stdout.readline().decode('UTF-8')
        print("TOOLS-" + self.service_id + " (read)", line.partition("\n")[0][:200])
        data = json.loads(line)
        return data

    def run(self):
        for data in iter(self.read_sync, b''):
            on_data = self.line_handlers.get(False) # don't block
            on_data(data)

        self.stdout.close()





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



class TypescriptEventListener(EventListener):

    def __init__(self):
        self.view_modified_time = 0

    # called whenever a veiw is focused
    def on_activated_async(self,view):
        print("on_activated_async", view.file_name())
        if not is_typescript(view): 
            self.current_view = None
            return
        
        self.current_view = view
        service = projects.service(view)
        # print(" - service", service.service_id)
        service.delegate = self
        service.add_file(view)
        service.check_errors()
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
        # self.mark_view_dirty(view)

        # immediately update
        service = projects.service(self.current_view)
        service.delegate = self
 
        service.update_file(self.current_view)
        service.check_errors_delay()
        service.invalidate_completions()

        # immediately check completions too?
        # service.load_completions_view(self.current_view)
        

    def on_typescript_errors(self, errors):
        if self.current_view:
            render_errors(self.current_view, errors)
        
    # # called a lot when selecting, AND each character
    def on_selection_modified_async(self, view):
        if not is_typescript(view): return

        service = projects.service(view)
        render_error_status(view, service.errors)

    # def on_post_save_async(self,view):
    #     print("on_post_save_async")

    def on_query_completions(self, view, prefix, locations):
        if not is_typescript(view): return

        print("******** on_query_completions")
        service = projects.service(view)
        
        if len(service.completions) == 0: 
            print(" - load")
            self.current_view = view
            service.load_completions_view(view, self.on_typescript_completions)
            return []

        else:
            print(" - render " + str(len(service.completions)))
            completions = list(map(completion_item, service.completions))
            return completions

    def on_typescript_completions(self, completions):
        self.current_view.run_command('hide_auto_complete')
        self.current_view.run_command('auto_complete',{
            'disable_auto_insert': True,
            'api_completions_only': True,
            'next_competion_if_showing': True
        })

                    
    # def on_query_context(self, view, key, operator, operand, match_all):
    #     if key == "typescript":
    #         view = sublime.active_window().active_view()
    #         return is_ts(view)        


def is_typescript(view=None):
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
        self.start = ErrorPosition(dict['start'])
        self.end = ErrorPosition(dict['end'])
        self.text = dict['text']
        self.phase = dict['phase']
        self.category = dict['category']

class ErrorPosition(object):
    def __init__(self, dict):
        self.line = dict['line']
        self.character = dict['character']    
