"""Shaders GLSL. O quad vem de gl_VertexID — nenhum vertex buffer de geometria."""

SPRITE_VS = """
#version 330
uniform vec2 u_view;  // (2/width, -2/height): pixels -> NDC com y para baixo

in vec2 in_pos;    // centro do sprite, em pixels (por instância)
in vec2 in_size;   // largura/altura em pixels (por instância)
in float in_rot;   // radianos (por instância)
in vec4 in_color;  // multiplicador RGBA (por instância)

out vec4 v_color;
out vec2 v_uv;

const vec2 CORNERS[4] = vec2[4](
    vec2(-0.5, -0.5), vec2(0.5, -0.5), vec2(-0.5, 0.5), vec2(0.5, 0.5)
);

void main() {
    vec2 corner = CORNERS[gl_VertexID] * in_size;
    float c = cos(in_rot);
    float s = sin(in_rot);
    vec2 world = in_pos + vec2(corner.x * c - corner.y * s,
                               corner.x * s + corner.y * c);
    gl_Position = vec4(world * u_view + vec2(-1.0, 1.0), 0.0, 1.0);
    v_uv = CORNERS[gl_VertexID] + 0.5;
    v_color = in_color;
}
"""

SPRITE_FS = """
#version 330
uniform sampler2D u_tex;

in vec4 v_color;
in vec2 v_uv;
out vec4 f_color;

void main() {
    f_color = texture(u_tex, v_uv) * v_color;
}
"""
