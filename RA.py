import streamlit as st
import os
import yaml
import subprocess
import tempfile
import base64
from pathlib import Path
import shutil
import time
import sys
import importlib
import io
import importlib.util
from PIL import Image

st.set_page_config(
    page_title="Riksarkivets Handskriftstranskribering",
    page_icon="📜",
    layout="wide"
)

# Sidtitel och introduktion
st.title("Riksarkivets Handskriftstranskribering")
st.markdown("""
## Transkribera handskrivna texter med Riksarkivets HTR Flow
Detta verktyg använder Riksarkivets HTR Flow för att transkribera handskrivna texter från bilder.
Läs mer på [Riksarkivets webbplats](https://riksarkivet.se/nyheter-och-press?item=120830).
""")

# Installationskontroll
@st.cache_resource
def initialize_environment():
    """Kontrollerar om HTR Flow är tillgängligt"""
    try:
        # Kontrollera om HTR Flow är installerat med importförsök
        try:
            import htrflow
            version = getattr(htrflow, "__version__", "okänd version")
            return True, f"HTR Flow är installerat (version: {version})"
        except ImportError:
            # Försök med kommandoradsversionen
            cmd_result = subprocess.run(
                ["which", "htrflow"] if os.name != 'nt' else ["where", "htrflow"],
                capture_output=True, 
                text=True, 
                check=False
            )
            
            if cmd_result.returncode == 0 and cmd_result.stdout.strip():
                return True, f"HTR Flow kommando hittades: {cmd_result.stdout.strip()}"
            
            return False, "HTR Flow är inte installerat. Kontrollera att det är inkluderat i requirements.txt."
    except Exception as e:
        return False, f"Ett fel uppstod vid kontroll av HTR Flow: {str(e)}"

# Skapa eller hämta pipeline.yaml
def create_pipeline_yaml(output_dir):
    """Skapar en standard pipeline.yaml-fil"""
    pipeline_config = {
        "steps": [
            {
                "step": "Segmentation",
                "settings": {
                    "model": "yolo",
                    "model_settings": {
                        "model": "Riksarkivet/yolov9-lines-within-regions-1"
                    }
                }
            },
            {
                "step": "TextRecognition",
                "settings": {
                    "model": "TrOCR",
                    "model_settings": {
                        "model": "Riksarkivet/trocr-base-handwritten-hist-swe-2"
                    }
                }
            },
            {
                "step": "OrderLines"
            },
            {
                "step": "Export",
                "settings": {
                    "format": "txt",
                    "dest": output_dir
                }
            }
        ]
    }
    
    # Returnera konfigurationen som en sträng
    return yaml.dump(pipeline_config, default_flow_style=False, sort_keys=False)

# Funktion som kör transkriberingen
def run_transcription(image_path, pipeline_path):
    """Kör HTR Flow för att transkribera bilden"""
    try:
        # Försök först att importera och använda Python API direkt
        try:
            import htrflow
            from htrflow.pipeline import Pipeline
            
            st.info("Använder HTR Flow Python API")
            
            # Läs pipeline-konfiguration
            with open(pipeline_path, 'r') as f:
                pipeline_config = yaml.safe_load(f)
            
            # Skapa och kör pipeline
            pipeline = Pipeline(pipeline_config)
            pipeline.run([image_path])
            
            return True, "Transkribering slutförd med Python API", ""
            
        except (ImportError, AttributeError) as e:
            st.warning(f"Kunde inte använda Python API: {e}. Försöker med kommandoradsversionen.")
            
            # Fallback till kommandoradsversionen
            command = f"htrflow pipeline {pipeline_path} {image_path}"
            
            # Kör kommandot och fånga utdata
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            return True, result.stdout, result.stderr
            
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return False, "", f"{str(e)}\n\n{tb}"

# Skapa en mock-implementation för demo-läge
def create_mock_module(temp_dir):
    """Skapar en mock-implementation av HTR Flow för demo-läge"""
    mock_module_path = os.path.join(temp_dir, "mock_htrflow.py")
    
    mock_code = """
# Mock-implementation av HTR Flow transkribering
import os
import time
import random
import yaml

class MockTranscriber:
    def __init__(self):
        self.demo_texts = [
            \"\"\"Monmouth den 29 1882.

Platskade Syster emot Svåger
Hå godt är min önskan
Jag får återigen göra försöket
att sända eder bref, jag har
förut skrifvitt men ej erhallett
någott wår från eder var. varför
jag tager det för troligt att
brefven icke har gått fram.
jag har erinu den stora gåfvan
att hafva en god helsa intill
skrifvande dag, och önskligt
voro att dessa rader trefar
eder vid samma goda gofva.
och jag får önska eder lycka
på det nya åratt samt god
fortsättning på detsamma.\"\"\",
            \"\"\"Stockholm den 15 juli 1876
            
Kära Syster!
Hjärtligt tack för Ditt bref
som jag mottog i går. Det
gläder mig mycket att höra
att Du och familjen mår väl.
Här i Stockholm är vädret
vackert men mycket varmt
dessa dagar. Jag hoppas
kunna besöka Eder i Augusti
om allt går som planerat.
Hälsa alla från mig!
Din tillgifne broder,
Carl\"\"\"
        ]
    
    def transcribe(self, image_path, output_dir):
        # Simulera bearbetningstid
        time.sleep(2 + random.random() * 3)
        
        # Välj en text baserat på filnamnet (deterministiskt)
        image_name = os.path.basename(image_path)
        hash_value = sum(ord(c) for c in image_name)
        text_index = hash_value % len(self.demo_texts)
        
        # Hämta texten
        transcribed_text = self.demo_texts[text_index]
        
        # Skapa utdatamappen om den inte finns
        os.makedirs(output_dir, exist_ok=True)
        
        # Spara resultatet
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}.txt")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcribed_text)
        
        return output_path

def mock_run_pipeline(pipeline_path, image_paths):
    # Läs pipeline-konfigurationen för att få utdatamappen
    with open(pipeline_path, "r", encoding="utf-8") as f:
        pipeline_config = yaml.safe_load(f)
    
    # Hitta export-steget för att få utdatamappen
    output_dir = None
    for step in pipeline_config.get("steps", []):
        if step.get("step") == "Export" and "settings" in step:
            output_dir = step["settings"].get("dest")
            break
    
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(image_paths[0]), "outputs")
        os.makedirs(output_dir, exist_ok=True)
    
    # Skapa en mock-transkribering för varje bild
    transcriber = MockTranscriber()
    for image_path in image_paths:
        transcriber.transcribe(image_path, output_dir)
    
    return True
"""
    
    with open(mock_module_path, "w", encoding="utf-8") as f:
        f.write(mock_code)
    
    return mock_module_path

# Huvudapp
def main():
    # Visa versionsinformation och miljö
    st.sidebar.header("Systeminformation")
    
    # Kontrollera om HTR Flow är tillgängligt
    success, message = initialize_environment()
    if success:
        st.sidebar.success(message)
    else:
        st.sidebar.error(message)
        st.sidebar.warning("""
        För att köra denna app med full funktionalitet behöver HTR Flow vara installerat.
        Appen kommer köras i demo-läge.
        """)
        
        # Visa debug-information
        with st.sidebar.expander("Debug-information"):
            st.code(f"Python version: {os.popen('python --version').read()}")
            st.code(f"Installerade paket:\n{os.popen('pip list').read()}")
            st.code(f"Systemversion: {os.popen('uname -a').read() if os.name != 'nt' else os.popen('ver').read()}")
    
    # Skapa temporära mappar för arbetet
    temp_dir = tempfile.mkdtemp()
    output_dir = os.path.join(temp_dir, "outputs")
    os.makedirs(output_dir, exist_ok=True)
    
    # Skapa pipeline.yaml
    pipeline_content = create_pipeline_yaml(output_dir)
    pipeline_path = os.path.join(temp_dir, "pipeline.yaml")
    
    with open(pipeline_path, "w") as f:
        f.write(pipeline_content)
    
    # Skapa mock-modul för demo-läge
    create_mock_module(temp_dir)
    
    # Visa konfigurationen i sidokolumnen
    with st.sidebar:
        st.header("Konfiguration")
        
        # Välj om demo-läge ska användas
        use_demo = st.checkbox("Använd demo-läge", value=not success)
        if use_demo:
            st.info("Demo-läge aktiverat. Transkribering simuleras utan att använda HTR Flow.")
        
        with st.expander("Pipeline-konfiguration"):
            st.code(pipeline_content, language="yaml")
            
            # Möjlighet att anpassa konfigurationen (enkel version)
            if st.checkbox("Anpassa pipeline-konfigurationen"):
                custom_pipeline = st.text_area(
                    "Redigera pipeline.yaml (avancerat)", 
                    value=pipeline_content,
                    height=400
                )
                
                if st.button("Uppdatera konfiguration"):
                    with open(pipeline_path, "w") as f:
                        f.write(custom_pipeline)
                    st.success("Konfigurationen har uppdaterats!")
    
    # Huvudinnehållet - uppladdning och transkribering
    st.header("Ladda upp en bild för transkribering")
    
    # Uppladdning av bild
    uploaded_file = st.file_uploader(
        "Välj en bild att transkribera", 
        type=["jpg", "jpeg", "png", "tif", "tiff"]
    )
    
    if uploaded_file:
        # Visa originalbild
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Originalbild")
            st.image(uploaded_file, use_column_width=True)
        
        # Spara den uppladdade filen
        image_path = os.path.join(temp_dir, uploaded_file.name)
        with open(image_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Transkribera bilden när användaren klickar på knappen
        if st.button("Transkribera bilden"):
            with st.spinner("Transkriberar... Detta kan ta några minuter."):
                # Mät processtiden
                start_time = time.time()
                
                if use_demo:
                    # Använd demo-läge
                    st.info("Använder demo-läge för transkribering")
                    
                    try:
                        # Läs in mock-modulen
                        sys.path.insert(0, temp_dir)
                        
                        import importlib.util
                        mock_module_path = os.path.join(temp_dir, "mock_htrflow.py")
                        spec = importlib.util.spec_from_file_location("mock_htrflow", mock_module_path)
                        mock_htrflow = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mock_htrflow)
                        
                        # Skapa en instans av MockTranscriber och transkribera bilden
                        transcriber = mock_htrflow.MockTranscriber()
                        mock_output_path = transcriber.transcribe(image_path, output_dir)
                        
                        success = True
                        stdout = f"Demo-transkribering slutförd. Resultat har sparats som {mock_output_path}"
                        stderr = ""
                    except Exception as e:
                        import traceback
                        success = False
                        stdout = ""
                        stderr = f"Fel vid körning av demo-transkribering: {str(e)}\n{traceback.format_exc()}"
                else:
                    # Kör transkriberingen med verklig HTR Flow
                    success, stdout, stderr = run_transcription(image_path, pipeline_path)
                
                # Processen är klar
                process_time = time.time() - start_time
                
                if success:
                    st.success(f"Transkriberingen slutfördes på {process_time:.2f} sekunder!")
                    
                    # Hitta den transkriberade filen
                    base_name = os.path.splitext(uploaded_file.name)[0]
                    output_file = os.path.join(output_dir, f"{base_name}.txt")
                    
                    if os.path.exists(output_file):
                        # Läs in resultatet
                        with open(output_file, "r", encoding="utf-8") as f:
                            transcribed_text = f.read()
                        
                        # Visa resultatet
                        with col2:
                            st.subheader("Transkriberad text")
                            st.text_area("", transcribed_text, height=400)
                            
                            # Skapa nedladdningsknapp för texten
                            st.download_button(
                                label="Ladda ner transkriberingen",
                                data=transcribed_text,
                                file_name=f"{base_name}_transkribering.txt",
                                mime="text/plain"
                            )
                    else:
                        st.error("Kunde inte hitta den transkriberade filen.")
                        st.code(f"Sökte efter: {output_file}")
                        
                        # Lista alla filer i output-katalogen
                        st.write("Filer i output-katalogen:")
                        all_files = []
                        for root, _, files in os.walk(output_dir):
                            for file in files:
                                all_files.append(os.path.join(root, file))
                        
                        if all_files:
                            for file_path in all_files:
                                st.write(f"- {file_path}")
                        else:
                            st.write("Inga filer hittades i output-katalogen.")
                else:
                    st.error("Transkriberingen misslyckades.")
                    
                    with st.expander("Visa felmeddelande"):
                        st.code(stdout)
                        st.code(stderr)
    
    # Rensa temporära filer när appen stängs
    def cleanup():
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    # Registrera upprensningsfunktionen
    import atexit
    atexit.register(cleanup)

if __name__ == "__main__":
    main()
