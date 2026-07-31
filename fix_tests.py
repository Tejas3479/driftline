import os

TEST_FILES = [
    "tests/test_anomalies.py",
    "tests/test_digests.py",
    "tests/test_forecasting.py",
    "tests/test_pipeline_evaluation.py",
    "tests/test_schema.py",
    "tests/test_ingestion.py",
    "tests/test_drivers.py",
]

for file_path in TEST_FILES:
    if not os.path.exists(file_path):
        continue
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.split('\n')
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Add db: AsyncSession to test functions
        if line.strip().startswith('async def test_') and '()' in line:
            uses_engine = False
            for j in range(i+1, min(i+50, len(lines))):
                if lines[j].strip().startswith('async def test_'):
                    break
                if 'create_async_engine' in lines[j]:
                    uses_engine = True
                    break
            if uses_engine:
                line = line.replace('()', '(db: AsyncSession)')
        
        # Replace engine creation block
        if 'test_engine = create_async_engine' in line:
            indent = line[:len(line) - len(line.lstrip())]
            j = i
            found_session = False
            while j < min(i+10, len(lines)):
                if 'async with async_session() as session:' in lines[j] or 'async with test_engine.connect() as conn:' in lines[j]:
                    if 'async with test_engine.connect() as conn:' in lines[j]:
                        while j < min(i+15, len(lines)):
                            if 'async with async_session() as session:' in lines[j]:
                                break
                            j += 1
                    found_session = True
                    break
                j += 1
            
            if found_session:
                i = j
                new_lines.append(indent + "session = db")
                new_lines.append(lines[j].replace('async with async_session() as session:', 'if True:'))
                i += 1
                continue
                
        # Remove test_engine.dispose()
        if 'await test_engine.dispose()' in line:
            i += 1
            continue
            
        new_lines.append(line)
        i += 1
        
    with open(file_path, "w", encoding="utf-8") as f:
        f.write('\n'.join(new_lines))
