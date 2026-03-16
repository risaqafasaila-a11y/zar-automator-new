import streamlit as st
import google.generativeai as genai
import time
import asyncio
import edge_tts
import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

# --- 1. KEAMANAN API KEY (MENGGUNAKAN SECRETS) ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ API Key tidak ditemukan! Masukkan GEMINI_API_KEY di menu Settings > Secrets pada Streamlit Cloud.")
    st.stop()

async def generate_voice(text, voice_name, output_path):
    communicate = edge_tts.Communicate(text, voice_name, rate="+0%")
    await communicate.save(output_path)

st.set_page_config(page_title="Zar's Video Automator Pro", layout="wide")
st.title("🎬 Zar's Video Automator Pro")
st.markdown("Automasi Video Cerdas dengan Deteksi Resolusi Otomatis")

# --- BAGIAN 1: INPUT VIDEO ---
st.subheader("1. Input Video")
uploaded_file = st.file_uploader("Pilih file video", type=['mp4', 'mov', 'avi'])
video_path = "temp_video.mp4"

if uploaded_file:
    with open(video_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Deteksi Resolusi Asli
    temp_clip = VideoFileClip(video_path)
    lebar, tinggi = temp_clip.size
    tipe_video = "Portrait (Tegak)" if tinggi > lebar else "Landscape (Mendatar)"
    st.info(f"📹 Video terdeteksi sebagai: **{tipe_video}** ({lebar}x{tinggi})")
    st.video(uploaded_file)
    temp_clip.close()

# --- BAGIAN 2: PENGATURAN KONTEN ---
st.subheader("2. Menu Pengaturan Konten")
col1, col2, col3 = st.columns(3)

with col1:
    voice_opt = st.selectbox("Pilih Karakter Suara:", ["Pria (Ardi)", "Wanita (Gadis)"])
    voice_map = {"Pria (Ardi)": "id-ID-ArdiNeural", "Wanita (Gadis)": "id-ID-GadisNeural"}

    gaya = st.selectbox("Gaya Bicara:", [
        "Dramatis", "Santai", "Formal", "Energetik",
        "Sarkas/Lucu", "Misterius", "Persuasif (Sales)",
        "Ceria", "Deep/Filosofis", "Komentator Bola"
    ])

with col2:
    bahasa = st.selectbox("Pilih Bahasa:", [
        "Bahasa Indonesia", "Bahasa Sunda", "Bahasa Jawa", "Bahasa Inggris", "Bahasa Jepang (Romaji)"
    ])

    kategori = st.selectbox("Tujuan Video:", [
        "Review Produk (Detail)", "Motivasi & Inspirasi", "Sinematik Showcase",
        "Bercerita/Storytelling", "Vlog Harian", "Hunting Koleksi",
        "Stand Up Comedy (Lucu)", "Dubbing / Parodi", "Fakta Unik"
    ])

with col3:
    st.write(" ")
    st.write(" ")
    create_btn = st.button("🚀 GENERATE FINAL VIDEO", use_container_width=True)

# --- INSTRUKSI TAMBAHAN ---
instruksi_user = st.text_area("✍️ Instruksi Tambahan (Opsional):",
                             placeholder="Contoh: Sebutkan nama channel 'Diecast Diorama', gunakan kata 'Gaskeun', atau mention PERSIB.")

# --- BAGIAN 3: PROSES AI & RENDERING ---
if create_btn and uploaded_file:
    video_clip = VideoFileClip(video_path)
    durasi_video = video_clip.duration

    with st.status("🤖 AI sedang memproses naskah & video...", expanded=True) as status:
        # Upload ke Gemini
        video_ai = genai.upload_file(path=video_path)
        while video_ai.state.name == "PROCESSING":
            time.sleep(2)
            video_ai = genai.get_file(video_ai.name)

        model = genai.GenerativeModel(model_name="gemini-3-flash-preview") # Gunakan model stabil

        estimasi_kata = int(durasi_video * 1.6)
        prompt = f"""Tonton video ini. Buat narasi suara untuk kategori {kategori} dalam {bahasa}.
        Gaya penulisan harus {gaya}.

        CATATAN KHUSUS DARI USER: {instruksi_user if instruksi_user else 'Tidak ada.'}

        ATURAN KETAT:
        1. LANGSUNG mulai narasi tanpa kalimat pembuka.
        2. Sesuaikan panjang kalimat agar pas untuk durasi {durasi_video} detik.
        3. Hanya output teks narasi saja."""

        response = model.generate_content([video_ai, prompt])
        naskah_clean = response.text.replace('"', '').strip()

        st.write(f"📝 **Naskah yang dihasilkan:**")
        st.write(naskah_clean)

        # Proses Suara
        st.write("🔊 Menghasilkan suara narasi...")
        asyncio.run(generate_voice(naskah_clean, voice_map[voice_opt], "vo.mp3"))

        # Audio Mixing
        st.write("🎬 Merakit video akhir...")
        audio_clip = AudioFileClip("vo.mp3")
        # Menjaga agar audio tidak melebihi durasi video
        audio_final = CompositeAudioClip([audio_clip.set_start(0)]).set_duration(durasi_video)

        # FINAL VIDEO (Otomatis mengikuti resolusi video_clip asli)
        final_video = video_clip.set_audio(audio_final)
        
        # Rendering (fps mengikuti file asli agar tidak patah-patah)
        output_name = "final_output.mp4"
        final_video.write_videofile(output_name, codec="libx264", audio_codec="aac", fps=video_clip.fps, preset="ultrafast")
        
        status.update(label="✅ Video Selesai Dibuat!", state="complete")

    st.success("Tonton dan download hasilnya di bawah ini:")
    st.video(output_name)

    with open(output_name, "rb") as file:
        st.download_button(label="📥 Download Video", data=file, file_name=f"ZarAutomator_{int(time.time())}.mp4")

    # Bersihkan file sementara (Optional)
    video_clip.close()
