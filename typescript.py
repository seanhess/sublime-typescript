import sublime, sublime_plugin

# NOTE: we need to load the whole project! Search for every file in the whole project and load it in to the plugin, no?
# As soon as you load something like that... 
# Simple commands: mark errors in the current file


# STEPS: 
# (1) get tss into the repo
# (2) when first typescript loaded
    # (z) print a message, and never do it again
    # (a) load tss process
    # (b) feed it all the typescript info in the whole project

# oh, but it should be per-project, right? 
# depends on how it works :)


service = None

class TypescriptService(object):
    blah = []

class TypescriptCheckCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return isTypescript(self.view)

    def run(self, edit):
        print("Typescript check", edit)

class TypescriptEventListener(sublime_plugin.EventListener):

    # called whenever a veiw is focused
    def on_activated_async(self,view):
        if(service == None):
            init()
        self.loaded = "loaded baby"
        print("on_activated_async", service, view.file_name())

    def on_clone_async(self,view):
        print("on_clone_async")

    def init_view(self,view):
        print("init_view")

    def on_load_async(self, view):
        print("on_load_async")

    # # called on each character sent
    # def on_modified_async(self, view):
    #     print("on_modified_async")
        
    # # called a lot when selecting, AND each character
    # def on_selection_modified_async(self, view):
    #     print("on_selection_modified_async")        

    # def on_post_save_async(self,view):
    #     print("on_post_save_async")

    
        

    # def handle_timeout(self,view):
    #     self.pending = self.pending -1
    #     if self.pending == 0:
    #         TSS.errors(view)


    # def on_query_completions(self, view, prefix, locations):
    #     if is_ts(view):
    #         pos = view.sel()[0].begin()
    #         (line, col) = view.rowcol(pos)
    #         is_member = str(is_member_completion(view.substr(sublime.Region(view.line(pos-1).a, pos)))).lower()
    #         TSS.complete(view,line,col,is_member)

    #         return COMPLETION_LIST


    # def on_query_context(self, view, key, operator, operand, match_all):
    #     if key == "typescript":
    #         view = sublime.active_window().active_view()
    #         return is_ts(view)        


def init():
    print("TYPESCRIPT init")
    global service
    service = TypescriptService()

def isTypescript(view=None):
    if view is None:
        view = sublime.active_window().active_view()
    return 'source.ts' in view.scope_name(0)

def plugin_loaded():
    settings = sublime.load_settings('typescript.sublime-settings')
    print("TS Loaded", settings)
    # sublime.set_timeout(lambda:init(sublime.active_window().active_view()), 300)
