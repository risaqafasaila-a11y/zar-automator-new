import streamlit as st
import google.generativeai as genai
import time
import asyncio
import edge_tts
import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, ColorClip, CompositeVideoClip

# --- 1. KEAMANAN API KEY (STREAMLIT SECRETS) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ API Key tidak ditemukan! Masukkan GEMINI_API_KEY di menu Settings > Secrets pada Streamlit Cloud.")
    st.stop()

async def generate_voice(text, voice_name, output_path):
    # Menggunakan rate sedikit lebih cepat agar narasi lebih dinamis
    communicate = edge_tts.Communicate(text, voice_name, rate="+5%")
    await communicate.save(output_path)

st.set_page_config(page_title="Zar's Video Automator Pro", layout="wide")
st.title("🎬 Zar's Video Automator Pro")
st.markdown("Automasi Video dengan Fitur **Multi-Format Export (TikTok & YouTube)**")

# --- BAGIAN 1: INPUT VIDEO ---
st.subheader("1. Input Video")
uploaded_file = st.file_uploader("Pilih file video", type=['mp4', 'mov', 'avi'])
video_path = "temp_video.mp4"

if uploaded_file:
    with open(video_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    with VideoFileClip(video_path) as temp_clip:
        w, h = temp_clip.size
        # Koreksi tampilan info jika ada metadata rotasi
        if temp_clip.rotation in [90, 270]:
            w, h = h, w
        tipe_video = "Portrait (Tegak)" if h > w else "Landscape (Mendatar)"
        st.info(f"📹 Video terdeteksi: **{tipe_video}** | Resolusi: {w}x{h} | FPS: {temp_clip.fps}")
        st.video(uploaded_file)

# --- BAGIAN 2: PENGATURAN KONTEN ---
st.subheader("2. Menu Pengaturan & Format")
col1, col2, col3 = st.columns(3)

with col1:
    voice_opt = st.selectbox("Pilih Karakter Suara:", ["Pria (Ardi)", "Wanita (Gadis)"])
    voice_map = {"Pria (Ardi)": "id-ID-ArdiNeural", "Wanita (Gadis)": "id-ID-GadisNeural"}
    gaya = st.selectbox("Gaya Bicara:", ["Energetik/Semangat", "Ceria/Friendly", "Dramatis", "Deep/Filosofis", "Formal/Profesional", "Santai/Conversational", "Persuasif (Sales)"])

with col2:
    bahasa = st.selectbox("Pilih Bahasa:", ["Bahasa Indonesia", "Bahasa Sunda", "Bahasa Jawa", "Bahasa Inggris"])
    kategori = st.selectbox("Tujuan Video:", ["Review Produk (Detail)", "Fakta Unik", "Soft Sell (Showcase)", "Cinematic Showcase", "Storytelling/Bercerita", "Vlog", "Menjawab Pertanyaan (Q&A)"])

with col3:
    # --- FITUR BARU: PILIHAN FORMAT OUTPUT ---
    format_output = st.radio("Pilih Format Output Akhir:", 
                             ["9:16 Portrait (TikTok/Shorts)", "16:9 Landscape (YouTube)"],
                             help="Pilih format tujuan video kamu.")
    create_btn = st.button("🚀 GENERATE FINAL VIDEO", use_container_width=True)

instruksi_user = st.text_area("✍️ Instruksi Tambahan (Opsional):", placeholder="Contoh: Sebutkan 'Gaskeun', gunakan kata 'Sobat Diecast', atau mention PERSIB.")

# --- BAGIAN 3: PROSES AI & RENDERING ---
if create_btn and uploaded_file:
    # 1. Load & Fix Physical Rotation
    video_clip = VideoFileClip(video_path)
    if video_clip.rotation in [90, 180, 270]:
        video_clip = video_clip.rotate(video_clip.rotation)
        video_clip.rotation = 0

    durasi_video = video_clip.duration

    with st.status("🤖 AI sedang memproses...", expanded=True) as status:
        # A. Analisis Visual Gemini
        st.write("🔍 Menganalisis video...")
        video_ai = genai.upload_file(path=video_path)
        while video_ai.state.name == "PROCESSING":
            time.sleep(2)
            video_ai = genai.get_file(video_ai.name)

        model = genai.GenerativeModel(model_name="gemini-3-flash-preview")
        prompt = f"""Tonton video ini. Buat narasi {kategori} dalam {bahasa} gaya {gaya}.
        Durasi: {durasi_video:.1f} detik. Instruksi: {instruksi_user}.
        HANYA output teks narasi saja, tanpa kata pembuka."""
        
        response = model.generate_content([video_ai, prompt])
        naskah_clean = response.text.replace('"', '').strip()
        st.write(f"📝 **Naskah AI:** {naskah_clean}")

        # B. Voice Over
        st.write("🔊 Menghasilkan suara...")
        asyncio.run(generate_voice(naskah_clean, voice_map[voice_opt], "vo.mp3"))
        audio_clip = AudioFileClip("vo.mp3")
        audio_final = CompositeAudioClip([audio_clip.set_start(0)]).set_duration(durasi_video)

        # C. LOGIKA FORMATTING (9:16 vs 16:9)
        st.write("📐 Menyesuaikan format frame...")
        
        # Tentukan target resolusi
        if "9:16" in format_output:
            target_w, target_h = 720, 1280
        else:
            target_w, target_h = 1280, 720
            
        # Background Hitam
        bg_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).set_duration(durasi_video)
        
        # Resize video asli agar muat di frame (Fit)
        # Menghitung rasio agar tidak gepeng
        video_aspect = video_clip.w / video_clip.h
        target_aspect = target_w / target_h
        
        if video_aspect > target_aspect:
            # Video lebih lebar dari target (misal Landscape mau ke Portrait)
            new_video = video_clip.resize(width=target_w)
        else:
            # Video lebih tinggi dari target (misal Portrait mau ke Landscape)
            new_video = video_clip.resize(height=target_h)
            
        # Gabungkan di tengah (Center)
        final_video_ui = CompositeVideoClip([bg_clip, new_video.set_position("center")])
        final_video_ui = final_video_ui.set_audio(audio_final)

        # D. Rendering
        output_name = f"ZarAI_{int(time.time())}.mp4"
        final_video_ui.write_videofile(
            output_name, 
            codec="libx264", 
            audio_codec="aac", 
            fps=video_clip.fps if video_clip.fps else 24, 
            preset="ultrafast",
            threads=4,
            ffmpeg_params=["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
        )
        status.update(label="✅ Selesai!", state="complete")

    st.success("Berhasil! Silakan cek hasil di bawah:")
    st.video(output_name)

    with open(output_name, "rb") as file:
        st.download_button(label="📥 Download Video", data=file, file_name=output_name)

    # Cleanup
    video_clip.close()
    audio_clip.close()
    final_video_ui.close()
