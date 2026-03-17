import streamlit as st
import google.generativeai as genai
import time
import asyncio
import edge_tts
import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

# --- 1. KONFIGURASI KEAMANAN (STREAMLIT SECRETS) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ API Key tidak ditemukan! Masukkan GEMINI_API_KEY di menu Settings > Secrets pada Streamlit Cloud.")
    st.stop()

async def generate_voice(text, voice_name, output_path):
    # Menggunakan rate +5% agar narasi terdengar lebih natural dan tidak terlalu lambat
    communicate = edge_tts.Communicate(text, voice_name, rate="+5%")
    await communicate.save(output_path)

st.set_page_config(page_title="Zar's Video Automator Pro", layout="wide")
st.title("🎬 Zar's Video Automator Pro")
st.markdown("Automasi Video dengan **Smart Orientation Detection** (Anti-Gepeng)")

# --- BAGIAN 1: INPUT VIDEO ---
st.subheader("1. Input Video")
uploaded_file = st.file_uploader("Pilih file video (MP4/MOV/AVI)", type=['mp4', 'mov', 'avi'])
video_path = "temp_video.mp4"

if uploaded_file:
    with open(video_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Deteksi Dimensi dengan Koreksi Metadata Rotasi
    with VideoFileClip(video_path) as temp_clip:
        w, h = temp_clip.size
        # Jika video memiliki metadata rotasi 90 atau 270, kita tukar dimensinya di info
        if temp_clip.rotation in [90, 270]:
            w, h = h, w
        
        tipe_video = "Portrait (Tegak)" if h > w else "Landscape (Mendatar)"
        st.info(f"📹 Video terdeteksi: **{tipe_video}** | Resolusi Asli: {w}x{h} | FPS: {temp_clip.fps}")
        st.video(uploaded_file)

# --- BAGIAN 2: PENGATURAN KONTEN ---
st.subheader("2. Menu Pengaturan Konten")
col1, col2, col3 = st.columns(3)

with col1:
    voice_opt = st.selectbox("Pilih Karakter Suara:", ["Pria (Ardi)", "Wanita (Gadis)"])
    voice_map = {"Pria (Ardi)": "id-ID-ArdiNeural", "Wanita (Gadis)": "id-ID-GadisNeural"}
    gaya = st.selectbox("Gaya Bicara:", [
        "Energetik/Semangat", "Ceria/Friendly", "Dramatis", "Deep/Filosofis", 
        "Formal/Profesional", "Santai/Conversational", "Otoriter/Tegas", 
        "Persuasif (Sales)", "Misterius/Suspense", "Sarkas/Lucu"
    ])

with col2:
    bahasa = st.selectbox("Pilih Bahasa:", ["Bahasa Indonesia", "Bahasa Sunda", "Bahasa Jawa", "Bahasa Inggris"])
    kategori = st.selectbox("Tujuan Video:", [
        "Review Produk (Detail)", "Fakta Unik", "Soft Sell (Showcase)", 
        "Hard Sell (Persuasif)", "Cinematic Showcase", "Storytelling/Bercerita", 
        "Stand Up Comedy/Parodi", "Motivasi & Inspirasi", "Menjawab Pertanyaan (Q&A)", 
        "Opini atau Reaksi (Reaction)", "Klarifikasi", "Ucapan Terima Kasih (Appreciation)", 
        "Hunting/Daily Vlog"
    ])

with col3:
    st.write(" ")
    st.write(" ")
    create_btn = st.button("🚀 GENERATE FINAL VIDEO", use_container_width=True)

instruksi_user = st.text_area("✍️ Instruksi Tambahan (Opsional):", 
                             placeholder="Contoh: Sebutkan 'Gaskeun', mention channel 'Zar Diecast', atau mention PERSIB.")

# --- BAGIAN 3: PROSES AI & RENDERING ---
if create_btn and uploaded_file:
    # 1. Load & Fix Physical Rotation
    video_clip = VideoFileClip(video_path)
    
    # Jika metadata rotasi ada, kita putar secara fisik agar frame-nya benar-benar tegak
    if video_clip.rotation in [90, 180, 270]:
        video_clip = video_clip.rotate(video_clip.rotation)
        video_clip.rotation = 0 # Penting: Reset agar tidak diputar ulang saat menyimpan

    durasi_video = video_clip.duration

    with st.status("🤖 AI sedang memproses...", expanded=True) as status:
        # A. Upload & Analisis Gemini
        st.write("🔍 Menganalisis visual video...")
        video_ai = genai.upload_file(path=video_path)
        while video_ai.state.name == "PROCESSING":
            time.sleep(2)
            video_ai = genai.get_file(video_ai.name)

        model = genai.GenerativeModel(model_name="gemini-3-flash-preview")
        prompt = f"""Tonton video ini. Buat naskah narasi {kategori} dalam {bahasa}.
        Gaya bicara: {gaya}. Durasi maksimal: {durasi_video:.1f} detik. 
        Instruksi Khusus: {instruksi_user if instruksi_user else 'Tidak ada'}.
        
        SYARAT:
        - Langsung ke narasi tanpa pembukaan.
        - Pastikan narasi selesai sebelum video habis."""
        
        response = model.generate_content([video_ai, prompt])
        naskah_clean = response.text.replace('"', '').strip()

        st.write(f"📝 **Naskah AI:** {naskah_clean}")

        # B. Voice Over
        st.write("🔊 Menghasilkan suara...")
        asyncio.run(generate_voice(naskah_clean, voice_map[voice_opt], "vo.mp3"))

        # C. Audio Mixing
        st.write("🎬 Merender video (Menerapkan Anti-Gepeng)...")
        audio_clip = AudioFileClip("vo.mp3")
        audio_final = CompositeAudioClip([audio_clip.set_start(0)]).set_duration(durasi_video)

        # D. Final Render
        final_video = video_clip.set_audio(audio_final)
        output_name = f"ZarAI_{int(time.time())}.mp4"
        
        final_video.write_videofile(
            output_name, 
            codec="libx264", 
            audio_codec="aac", 
            fps=video_clip.fps if video_clip.fps else 24, 
            preset="ultrafast",
            threads=4,
            # Parameter FFmpeg untuk memastikan lebar/tinggi genap & menjaga rasio
            ffmpeg_params=["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
        )
        
        status.update(label="✅ Selesai!", state="complete")

    st.success("Berhasil! Silakan cek hasil di bawah:")
    st.video(output_name)

    with open(output_name, "rb") as file:
        st.download_button(label="📥 Download Video", data=file, file_name=output_name)

    # Cleanup memori agar aplikasi tetap ringan
    video_clip.close()
    if 'audio_clip' in locals(): audio_clip.close()
