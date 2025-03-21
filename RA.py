import streamlit as st
import os
import tempfile
import sys
import yaml
import subprocess
from pathlib import Path
import time
import base64

st.set_page_config(
    page_title="Handskriftstranskribering med Riksarkivets HTR Flow",
    page_icon="📜",
    layout="wide"
)

# Sidotitel och introduktion
st.title("Handskriftstranskribering med Riksarkivets HTR Flow")
st.markdown("""
## Introduktion
Detta verktyg använder Riksarkivets HTR Flow för att transkribera handskriven text från bilder. 
Programmet delar upp bilden i rader, analyserar texten, och genererar en transkription.

[Läs mer om Riksarkivets projekt](https://riksarkivet.se/nyheter-och-press?item=120830)
""")

# Kontrollera om HTR Flow är installerat
try:
    import htrflow
    st.success("HTR Flow är installerat och redo att användas.")
except ImportError:
    st.error("""
    HTR Flow är inte installerat på detta system. 
    
    För att köra denna app behöver du installera HTR Flow i förväg genom att köra:
    ```
    pip install htrflow
    ```
    
    Om du har problem med installationen, prova följande:
    1. Se till att du använder Python 3.8 eller senare
    2. Installera alla nödvändiga beroenden för HTR Flow
    3. Prova att använda den Docker-baserade installationen (se dokumentationen)
    """)
    
    with st.expander("Försök installera automatiskt (kan misslyckas)"):
        if st.button("Försök installera HTR Flow"):
            try:
                st.info("Försöker installera HTR Flow. Detta kan ta flera minuter...")
                from pip import _internal
                _internal.main(['install', 'htrflow'])
                st.success("Installation verkar ha lyckats! Starta om appen.")
            except Exception as e:
                st.error(f"Installationen misslyckades: {e}")
                st.info("Försök med manuell installation eller Docker-alternativet.")
    
    with st.expander("Teknisk information"):
        st.write(f"Python-version: {sys.version}")
        st.write(f"Sökväg till Python: {sys.executable}")
        if st.button("Visa installerade paket"):
            try:
                import pkg_resources
                packages = sorted([f"{p.key} {p.version}" for p in pkg_resources.working_set])
                st.code("\n".join(packages))
            except:
                st.error("Kunde inte visa installerade paket.")
    
    st.stop()  # Stoppa appen här för att undvika ytterligare felmeddelanden

# Skapa temporärt utrymme att arbeta i
temp_dir = tempfile.mkdtemp()
output_dir = os.path.join(temp_dir, "outputs")
os.makedirs(output_dir, exist_ok=True)

# Skapa en standardpipeline.yaml om användaren inte laddar upp en egen
default_pipeline = {
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

# Sidebar för konfigurationer
with st.sidebar:
    st.header("Konfiguration")
    
    # Val av konfigurationsmetod
    config_option = st.radio(
        "Välj konfigurationsmetod:",
        ["Använd standardinställningar", "Anpassa inställningar", "Ladda upp egen YAML-fil"]
    )
    
    if config_option == "Använd standardinställningar":
        pipeline_config = default_pipeline
        
    elif config_option == "Anpassa inställningar":
        st.subheader("Segmentering")
        seg_model = st.selectbox(
            "Segmenteringsmodell:", 
            ["Riksarkivet/yolov9-lines-within-regions-1"], 
            index=0
        )
        
        st.subheader("Textigenkänning")
        text_model = st.selectbox(
            "Textigenkänningsmodell:", 
            ["Riksarkivet/trocr-base-handwritten-hist-swe-2"], 
            index=0
        )
        
        # Uppdatera pipeline med användarinställningar
        pipeline_config = default_pipeline.copy()
        pipeline_config["steps"][0]["settings"]["model_settings"]["model"] = seg_model
        pipeline_config["steps"][1]["settings"]["model_settings"]["model"] = text_model
        
    elif config_option == "Ladda upp egen YAML-fil":
        uploaded_yaml = st.file_uploader("Ladda upp pipeline.yaml", type=["yaml", "yml"])
        if uploaded_yaml:
            try:
                pipeline_config = yaml.safe_load(uploaded_yaml)
                st.success("YAML fil laddad!")
            except Exception as e:
                st.error(f"Fel vid inläsning av YAML: {e}")
                pipeline_config = default_pipeline
        else:
            pipeline_config = default_pipeline
    
    # Se till att output-katalogen är inställd till vår temporära katalog
    if "steps" in pipeline_config and isinstance(pipeline_config["steps"], list):
        for step in pipeline_config["steps"]:
            if step.get("step") == "Export":
                if "settings" not in step:
                    step["settings"] = {}
                step["settings"]["dest"] = output_dir

# Spara pipeline-konfigurationen till en fil
pipeline_path = os.path.join(temp_dir, "pipeline.yaml")
with open(pipeline_path, 'w') as f:
    yaml.dump(pipeline_config, f)

# Funktion för att visa inlästa bilder
def display_image(image_path):
    with open(image_path, "rb") as img_file:
        img_bytes = img_file.read()
        encoded = base64.b64encode(img_bytes).decode()
        st.image(
            img_bytes,
            caption="Uppladdad bild",
            use_column_width=True
        )

# Funktion för att köra HTR Flow och visa resultatet
def run_htr_flow(image_path, pipeline_path):
    image_filename = os.path.basename(image_path)
    image_name = os.path.splitext(image_filename)[0]
    
    with st.spinner("Transkriberar... Detta kan ta några minuter."):
        start_time = time.time()
        try:
            # Försök att köra HTR Flow som ett Python-bibliotek direkt
            try:
                from htrflow.cli.pipeline import run_pipeline
                
                # Anropa run_pipeline med korrekt konfiguration
                run_pipeline(pipeline_path, [image_path])
                
                st.info("HTR Flow kördes med Python API")
                
            except (ImportError, AttributeError) as e:
                # Fallback till kommandoradsversion om Python API inte fungerar
                st.warning(f"Försöker med kommandoradsversionen: {e}")
                
                # Skapa kommandot
                command = f"htrflow pipeline {pipeline_path} {image_path}"
                
                # Kör kommandot och fånga utmatningen
                result = subprocess.run(
                    command, 
                    shell=True, 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                
                # Visa eventuell utmatning i en expandable section
                with st.expander("Visa processinformation"):
                    st.code(result.stdout)
                    if result.stderr:
                        st.error(result.stderr)
            
            # Hitta och visa den genererade textfilen
            output_filename = f"{image_name}.txt"
            found_output = False
            
            for root, _, files in os.walk(output_dir):
                for file in files:
                    if file == output_filename:
                        output_path = os.path.join(root, file)
                        with open(output_path, 'r', encoding='utf-8') as f:
                            transcribed_text = f.read()
                        
                        st.success(f"Transkribering slutförd på {time.time() - start_time:.2f} sekunder!")
                        found_output = True
                        return transcribed_text
            
            if not found_output:
                st.warning(f"Kunde inte hitta utdatafilen '{output_filename}'. Kontrollera att export-sökvägen i pipeline.yaml är korrekt.")
                # Lista filer i output-katalogen för felsökning
                st.write("Filer i output-katalogen:")
                for root, _, files in os.walk(output_dir):
                    for file in files:
                        st.write(f" - {os.path.join(root, file)}")
                return None
            
        except Exception as e:
            st.error(f"Ett fel uppstod vid körning av HTR Flow: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None

# Huvuddelen av applikationen
st.header("Ladda upp bild för transkribering")

uploaded_file = st.file_uploader("Välj en bild för transkribering", type=["jpg", "jpeg", "png", "tif", "tiff"])

if uploaded_file:
    # Spara den uppladdade filen temporärt
    image_path = os.path.join(temp_dir, uploaded_file.name)
    with open(image_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Visa den uppladdade bilden
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original")
        display_image(image_path)
    
    # Knapp för att starta transkriberingen
    if st.button("Starta transkribering"):
        with col2:
            st.subheader("Transkriberad text")
            transcribed_text = run_htr_flow(image_path, pipeline_path)
            
            if transcribed_text:
                st.text_area("Resultat", transcribed_text, height=400)
                
                # Erbjud nedladdning av resultatet
                st.download_button(
                    label="Ladda ner transkriptionen",
                    data=transcribed_text,
                    file_name=f"{os.path.splitext(uploaded_file.name)[0]}_transkription.txt",
                    mime="text/plain"
                )

# Funktionalitet för batch-transkribering
st.header("Batch-transkribering")
st.markdown("""
För att transkribera flera bilder samtidigt, ladda upp dem här. 
Alla bilder kommer att transkriberas och resultaten kan laddas ner som en zip-fil.
""")

batch_files = st.file_uploader("Välj bilder för batch-transkribering", 
                              type=["jpg", "jpeg", "png", "tif", "tiff"], 
                              accept_multiple_files=True)

if batch_files:
    st.write(f"{len(batch_files)} bilder valda för batch-transkribering")
    
    batch_temp_dir = os.path.join(temp_dir, "batch")
    os.makedirs(batch_temp_dir, exist_ok=True)
    
    # Spara alla uppladdade filer
    image_paths = []
    for uploaded_file in batch_files:
        image_path = os.path.join(batch_temp_dir, uploaded_file.name)
        with open(image_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        image_paths.append(image_path)
    
    if st.button("Starta batch-transkribering"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = {}
        for i, image_path in enumerate(image_paths):
            status_text.text(f"Transkriberar bild {i+1} av {len(image_paths)}: {os.path.basename(image_path)}")
            
            transcribed_text = run_htr_flow(image_path, pipeline_path)
            if transcribed_text:
                results[os.path.basename(image_path)] = transcribed_text
            
            progress_bar.progress((i + 1) / len(image_paths))
        
        if results:
            # Skapa en sammanfattning av alla transkriptioner
            all_text = "\n\n=== TRANSKRIPTION AV {} ===\n\n".format
            combined_text = "\n\n".join(all_text(name) + text for name, text in results.items())
            
            st.success(f"Batch-transkribering slutförd! {len(results)} av {len(image_paths)} bilder transkriberades.")
            
            st.download_button(
                label="Ladda ner alla transkriptioner (textfil)",
                data=combined_text,
                file_name="batch_transkriptioner.txt",
                mime="text/plain"
            )
            
            # Visa ett exempel på resultatet
            with st.expander("Visa exempel på transkriptioner"):
                for name, text in list(results.items())[:3]:  # Visa endast de första 3 för överskådlighet
                    st.subheader(name)
                    st.text_area(f"Transkription av {name}", text, height=200)
                if len(results) > 3:
                    st.info(f"... och {len(results) - 3} fler transkriptioner")

# Instruktioner för användning
with st.expander("Instruktioner för användning"):
    st.markdown("""
    ### Hur man använder verktyget

    1. **Enskild bild**:
       - Ladda upp en bild på den handskrivna texten.
       - Klicka på "Starta transkribering".
       - Vänta medan transkriberingen utförs.
       - Resultatet visas i textfältet till höger och kan laddas ner.

    2. **Batch-transkribering**:
       - Ladda upp flera bilder.
       - Klicka på "Starta batch-transkribering".
       - Vänta tills alla bilder har transkriberats.
       - Ladda ner resultaten som en samlad textfil.

    3. **Konfiguration**:
       - I sidofältet kan du välja att använda standardinställningar, anpassa inställningar eller ladda upp en egen YAML-konfigurationsfil.
       - Standardinställningarna använder Riksarkivets modeller för svensk handskrift.

    ### Om tekniken
    
    Verktyget använder HTR Flow från Riksarkivet som bygger på AI-modeller tränade specifikt för svenska historiska handskrifter. Processen omfattar:
    
    1. **Segmentering**: Bilden analyseras för att identifiera textrader.
    2. **Textigenkänning**: Varje identifierad textrad tolkas med en AI-modell.
    3. **Radarrangemang**: Raderna ordnas i läsordning.
    4. **Export**: Resultatet sparas som textfil.
    """)

# Footer med information
st.markdown("---")
st.markdown("""
*Denna app bygger på [Riksarkivets HTR Flow](https://riksarkivet.se/nyheter-och-press?item=120830) 
för transkribering av handskrifter. Alla rättigheter till underliggande modeller tillhör Riksarkivet.*
""")