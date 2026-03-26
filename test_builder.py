import time
import sys

print('1. Importing TemplateBuilder...')
start_import = time.time()
from services.template_builder import TemplateBuilder
print(f'2. Imported in {time.time()-start_import:.2f}s. Initializing builder...')

start_init = time.time()
b = TemplateBuilder()
print(f'3. Initialized in {time.time()-start_init:.2f}s. Calling build_from_document...')

start_build = time.time()
try:
    res = b.build_from_document('Company: NovaTech Solutions\nMission: Great stuff.')
    print(f'4. Finished build in {time.time()-start_build:.2f}s! Brand:', res.brand_name)
except Exception as e:
    print(f"Error during build: {e}")
    import traceback
    traceback.print_exc()
