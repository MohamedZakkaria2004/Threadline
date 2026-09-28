"""Read-only runtime inventory without Windows WMI or credential disclosure."""
import ctypes
import json
import os
import sys
from app.config import ROOT, Settings
from app.storage import now

def main():
    settings = Settings()
    report = {'at':now(),'python':sys.version,'processor':os.getenv('PROCESSOR_IDENTIFIER'),
              'logical_cpus':os.cpu_count(),'data_dir':str(settings.data_dir),'model':settings.model,
              'embedding_model':settings.embed_model,'prompt_version':settings.prompt_version,
              'ollama_url':settings.ollama_url,'port':os.getenv('COPILOT_PORT','8765')}
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong)] + [(name,ctypes.c_ulonglong) for name in ('total_physical','available_physical','total_page_file','available_page_file','total_virtual','available_virtual','extended_virtual')]
        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            report['memory'] = {name:getattr(memory,name) for name,_ in memory._fields_ if name!='length'}
    (ROOT / 'artifacts' / 'e2e-audit-runtime-inventory.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
