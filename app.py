import streamlit as st
import google.generativeai as genai
import time
import asyncio
import edge_tts
import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, ColorClip, CompositeVideoClip

# --- 1. KONFIGURASI KEAMANAN ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ API Key tidak ditemukan di Secrets.")
    st.stop()

async def generate_voice(text, voice_name, output_path):
    communicate = edge_tts.Communicate(text, voice_name, rate="+5%")
    await communicate.save(output_path)

st.set_page_config(page_title="Zar's Video Automator Pro", layout="wide")
st.title("🎬 Zar's Video Automator Pro")

# --- BAGIAN 1: INPUT VIDEO ---
st.subheader("1. Input Video")
uploaded_file = st.file_uploader("Pilih file video", type=['mp4', 'mov', 'avi'])
video_path = "temp_video.mp4"

if uploaded_file:
    with open(video_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.video(uploaded_file)

# --- BAGIAN 2: PENGATURAN ---
st.subheader("2. Menu Pengaturan & Format")
col1, col2, col3 = st.columns(3)

with col1:
    voice_opt = st.selectbox("Pilih Suara:", ["Pria (Ardi)", "Wanita (Gadis)"])
    voice_map = {"Pria (Ardi)": "id-ID-ArdiNeural", "Wanita (Gadis)": "id-ID-GadisNeural"}
    gaya = st.selectbox("Gaya Bicara:", ["Energetik", "Ceria", "Dramatis", "Formal", "Santai"])

with col2:
    bahasa = st.selectbox("Pilih Bahasa:", ["Bahasa Indonesia", "Bahasa Sunda", "Bahasa Jawa"])
    kategori = st.selectbox("Tujuan Video:", ["Review Produk", "Vlog", "Cinematic", "Storytelling"])

with col3:
    # --- FITUR BARU: PILIHAN FORMAT ---
    format_output = st.radio("Format Output Akhir:", 
                             ["9:16 Portrait (TikTok/Shorts)", "16:9 Landscape (YouTube)"])
    create_btn = st.button("🚀 GENERATE FINAL VIDEO", use_container_width=True)

instruksi_user = st.text_area("✍️ Instruksi Tambahan (Opsional):")

# --- BAGIAN 3: PROSES AI & RENDERING ---
if create_btn and uploaded_file:
    # 1. Load & Fix Rotation
    video_clip = VideoFileClip(video_path)
    if video_clip.rotation in [90, 180, 270]:
        video_clip = video_clip.rotate(video_clip.rotation)
        video_clip.rotation = 0

    durasi_video = video_clip.duration

    with st.status("🤖 Memproses Video...", expanded=True) as status:
        # A. Gemini Analysis
        video_ai = genai.upload_file(path=video_path)
        while video_ai.state.name == "PROCESSING":
            time.sleep(2)
            video_ai = genai.get_file(video_ai.name)

        model = genai.GenerativeModel(model_name="gemini-3-flash-preview")
        prompt = f"Buat narasi {kategori} dalam {bahasa} gaya {gaya}. Durasi {durasi_video:.1f}s. {instruksi_user}"
        response = model.generate_content([video_ai, prompt])
        naskah_clean = response.text.strip().replace('"', '')

        # B. Voice Over
        asyncio.run(generate_voice(naskah_clean, voice_map[voice_opt], "vo.mp3"))
        audio_clip = AudioFileClip("vo.mp3")
        audio_final = CompositeAudioClip([audio_clip.set_start(0)]).set_duration(durasi_video)

        # C. RESIZE LOGIC (Anti-Gepeng untuk antar platform)
        st.write("📐 Menyesuaikan format video...")
        
        target_w, target_h = (720, 1280) if "9:16" in format_output else (1280, 720)
        
        # Resize video asli agar muat di target tanpa gepeng (fit)
        video_resized = video_clip.resize(height=target_h) if "9:16" in format_output else video_clip.resize(width=target_w)
        
        # Jika masih lebih lebar/tinggi dari target, kita resize ulang berdasarkan sisi satunya
        if video_resized.w > target_w: video_resized = video_clip.resize(width=target_w)
        if video_resized.h > target_h: video_resized = video_clip.resize(height=target_h)

        # Buat background hitam agar sisa ruang tertutup
        bg = ColorClip(size=(target_w, target_h), color=(0,0,0)).set_duration(durasi_video)
        
        # Gabungkan video asli di atas background hitam (Center)
        final_ui_video = CompositeVideoClip([bg, video_resized.set_position("center")])
        final_ui_video = final_ui_video.set_audio(audio_final)

        # D. Rendering
        output_name = f"ZarAI_{int(time.time())}.mp4"
        final_ui_video.write_videofile(
            output_name, 
            codec="libx264", 
            audio_codec="aac", 
            fps=24, 
            preset="ultrafast",
            ffmpeg_params=["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
        )
        status.update(label="✅ Selesai!", state="complete")

    st.video(output_name)
    with open(output_name, "rb") as file:
        st.download_button(label="📥 Download Video", data=file, file_name=output_name)

    video_clip.close()
