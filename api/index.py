from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import base64
import io
import os

# Locate the templates folder reliably on Vercel
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Standard Indonesian e-KTP coordinates in percentages (x, y, width, height)
KTP_COORDINATES = {
    'nik':    (0.24, 0.18, 0.45, 0.08),
    'nama':   (0.26, 0.28, 0.43, 0.06),
    'ttl':    (0.26, 0.34, 0.43, 0.06),
    'alamat': (0.26, 0.46, 0.43, 0.18),
    'foto':   (0.71, 0.20, 0.25, 0.48),
    'ttd':    (0.73, 0.76, 0.21, 0.15)
}

def get_safe_font(size=22):
    # Try loading Pillow's sized default font; fallback safely if unsupported
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/proses-ktp', methods=['POST'])
def proses_ktp():
    try:
        data = request.json
        image_data = data.get('image')
        selected_fields = data.get('fields', [])
        watermark_text = data.get('watermark', '').strip()
        censor_mode = data.get('mode', 'black')

        # 1. Decode Base64 image
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        width, height = img.size

        draw = ImageDraw.Draw(img)

        # 2. Apply Censoring
        for field in selected_fields:
            if field in KTP_COORDINATES:
                rx, ry, rw, rh = KTP_COORDINATES[field]
                x1 = int(rx * width)
                y1 = int(ry * height)
                x2 = int((rx + rw) * width)
                y2 = int((ry + rh) * height)

                if censor_mode == 'blur':
                    cropped_area = img.crop((x1, y1, x2, y2))
                    blurred_area = cropped_area.filter(ImageFilter.GaussianBlur(radius=15))
                    img.paste(blurred_area, (x1, y1))
                else:
                    draw.rectangle([x1, y1, x2, y2], fill=(0, 0, 0, 255))

        # 3. Apply Diagonal Watermark
        if watermark_text:
            txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
            txt_draw = ImageDraw.Draw(txt_layer)

            words = watermark_text.split(' ')
            lines = []
            current_line = ''
            for word in words:
                if len(current_line + word) > 38:
                    lines.append(current_line.strip())
                    current_line = word + ' '
                else:
                    current_line += word + ' '
            if current_line:
                lines.append(current_line.strip())

            font = get_safe_font(size=22)

            y_offsets = [int(height * 0.2), int(height * 0.45), int(height * 0.7)]
            for start_y in y_offsets:
                for idx, line in enumerate(lines):
                    y_pos = start_y + (idx * 26)
                    txt_draw.text(
                        (int(width * 0.12), y_pos),
                        line,
                        font=font,
                        fill=(255, 255, 255, 160),
                        stroke_width=2,
                        stroke_fill=(0, 0, 0, 120)
                    )

            rotated_txt = txt_layer.rotate(15, resample=Image.BICUBIC, expand=False)
            img = Image.alpha_composite(img, rotated_txt)

        # 4. Return processed JPEG
        final_img = img.convert("RGB")
        buffered = io.BytesIO()
        final_img.save(buffered, format="JPEG", quality=92)
        result_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return jsonify({
            'status': 'success',
            'result_image': f"data:image/jpeg;base64,{result_base64}"
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)