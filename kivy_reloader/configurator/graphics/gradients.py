# https://github.com/Sahil-pixel
from kivy.graphics import Color, Fbo, Rectangle
from kivy.graphics.opengl import GL_BLEND, glEnable


class GLGradient:
    @staticmethod
    def radial(border_color=(1, 1, 0, 0), center_color=(1, 0, 0, 1), size=(64, 64)):
        fbo = Fbo(size=size)
        fbo.shader.fs = """
        $HEADER$
        uniform vec4 border_color;
        uniform vec4 center_color;
        void main (void) {
            float d = clamp(distance(tex_coord0, vec2(0.5, 0.5)), 0., 1.);
            gl_FragColor = mix(center_color, border_color, d);
        }
        """
        fbo['border_color'] = list(map(float, border_color))
        fbo['center_color'] = list(map(float, center_color))
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def vertical(top_color=(1, 1, 1, 1), bottom_color=(0, 0, 0, 0), size=(64, 64)):
        fbo = Fbo(size=size)
        fbo.shader.fs = """
        $HEADER$
        uniform vec4 top_color;
        uniform vec4 bottom_color;
        void main (void) {
            float t = tex_coord0.y;
            gl_FragColor = mix(bottom_color, top_color, t);
        }
        """
        fbo['top_color'] = list(map(float, top_color))
        fbo['bottom_color'] = list(map(float, bottom_color))
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def horizontal(left_color=(1, 0, 0, 0), right_color=(0, 0, 1, 1), size=(64, 64)):
        fbo = Fbo(size=size)
        fbo.shader.fs = """
        $HEADER$
        uniform vec4 left_color;
        uniform vec4 right_color;
        void main (void) {
            float t = clamp(tex_coord0.x, 0., 1.);
            gl_FragColor = mix(left_color, right_color, t);
        }
        """
        fbo['left_color'] = list(map(float, left_color))
        fbo['right_color'] = list(map(float, right_color))
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def diagonal(start_color=(1, 0, 1, 1), end_color=(0, 1, 1, 0), size=(64, 64)):
        fbo = Fbo(size=size)
        fbo.shader.fs = """
        $HEADER$
        uniform vec4 start_color;
        uniform vec4 end_color;
        void main (void) {
            float diag = clamp((tex_coord0.x + tex_coord0.y) / 2.0, 0., 1.);
            gl_FragColor = mix(start_color, end_color, diag);
        }
        """
        fbo['start_color'] = list(map(float, start_color))
        fbo['end_color'] = list(map(float, end_color))
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def reverse_diagonal(
        start_color=(1, 1, 0, 0.2), end_color=(0, 0, 1, 1), size=(64, 64)
    ):
        fbo = Fbo(size=size)
        fbo.shader.fs = """
        $HEADER$
        uniform vec4 start_color;
        uniform vec4 end_color;
        void main (void) {
            float diag = clamp((1.0 - tex_coord0.x + tex_coord0.y) / 2.0, 0., 1.);
            gl_FragColor = mix(start_color, end_color, diag);
        }
        """
        fbo['start_color'] = list(map(float, start_color))
        fbo['end_color'] = list(map(float, end_color))
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def corner(
        tl=(1.0, 0.0, 0.0, 1.0),
        tr=(0.0, 1.0, 0.0, 1.0),
        bl=(0.0, 0.0, 1.0, 1.0),
        br=(1.0, 1.0, 0.0, 1.0),
        size=(64, 64),
    ):
        fbo = Fbo(size=size, with_stencilbuffer=False)
        fbo.shader.fs = """
        $HEADER$
        uniform vec4 tl;
        uniform vec4 tr;
        uniform vec4 bl;
        uniform vec4 br;
        void main (void) {
            vec2 uv = tex_coord0.xy;
            vec4 top = mix(tl, tr, uv.x);
            vec4 bottom = mix(bl, br, uv.x);
            gl_FragColor = mix(bottom, top, uv.y);
        }
        """
        fbo['tl'] = list(map(float, tl))
        fbo['tr'] = list(map(float, tr))
        fbo['bl'] = list(map(float, bl))
        fbo['br'] = list(map(float, br))
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def diamond(start_color=(0, 1, 0, 1), end_color=(0, 0, 1, 0.5), size=(64, 64)):
        fbo = Fbo(size=size)
        fbo.shader.fs = """
        $HEADER$
        uniform vec4 start_color;
        uniform vec4 end_color;
        void main (void) {
            vec2 uv = tex_coord0.xy - 0.5;
            float dist = abs(uv.x) + abs(uv.y);
            float t = clamp(dist / 0.5, 0.0, 1.0);
            gl_FragColor = mix(start_color, end_color, t);
        }
        """
        fbo['start_color'] = list(map(float, start_color))
        fbo['end_color'] = list(map(float, end_color))
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def sweep(size=(64, 64), colors=None, stops=None):
        if not colors:
            colors = [
                (1.0, 0.0, 0.0, 1.0),
                (0.0, 1.0, 0.0, 1.0),
                (0.0, 0.0, 1.0, 1.0),
                (1.0, 1.0, 0.0, 1.0),
                (1.0, 0.0, 0.0, 1.0),
            ]
        n = len(colors)
        stops = stops or [i / (n - 1) for i in range(n)]
        fbo = Fbo(size=size, with_stencilbuffer=False)

        # color_array = ',\n'.join(f'vec4({",".join(map(str, c))})' for c in colors)
        # stop_array = ', '.join(f'{s:.5f}' for s in stops)

        fbo.shader.fs = f"""
        $HEADER$
        #define N {n}
        uniform vec4 colors[N];
        uniform float stops[N];
        void main(void) {{
            vec2 uv = tex_coord0.xy * 2.0 - 1.0;
            float angle = atan(uv.y, uv.x);
            float norm_angle = (angle + 3.1415926) / (2.0 * 3.1415926);
            vec4 color = colors[0];
            for (int i = 0; i < N - 1; ++i) {{
                if (norm_angle >= stops[i] && norm_angle <= stops[i + 1]) {{
                    float t = (norm_angle - stops[i]) / (stops[i + 1] - stops[i]);
                    color = mix(colors[i], colors[i + 1], t);
                    break;
                }}
            }}
            gl_FragColor = color;
        }}
        """

        for i, c in enumerate(colors):
            fbo[f'colors[{i}]'] = list(c)
        fbo['stops'] = stops
        with fbo:
            glEnable(GL_BLEND)
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture

    @staticmethod
    def radial_rainbow(size=(256, 256), base_hue=0.0):
        fbo = Fbo(size=size, with_stencilbuffer=False)
        fbo.shader.fs = """
        $HEADER$
        uniform vec2 resolution;
        uniform float base_hue;

        vec3 hsv2rgb(vec3 c) {
            vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
            vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
            return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
        }

        void main(void) {
            vec2 uv = gl_FragCoord.xy / resolution.xy;
            vec2 center = vec2(0.5, 0.5);
            vec2 delta = uv - center;
            float angle = atan(delta.y, delta.x) / 6.2831 + 0.5;
            float dist = length(delta) / 0.7071;
            float hue = mod(angle + base_hue, 1.0);
            vec3 color = hsv2rgb(vec3(hue, 1.0, 1.0 - dist));
            gl_FragColor = vec4(color, 1.0 - dist);
        }
        """
        fbo['resolution'] = list(map(float, size))
        fbo['base_hue'] = float(base_hue)
        with fbo:
            Color(1, 1, 1, 1)
            Rectangle(size=size)
        fbo.draw()
        return fbo.texture
