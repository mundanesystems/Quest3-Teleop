Shader "Unlit/StereoPassthroughShader"
{
    Properties
    {
        _MainTex ("Texture", 2D) = "white" {}
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 100

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            // Tell the shader to compile for VR
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            sampler2D _MainTex;
            float4 _MainTex_ST;

            v2f vert (appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o); // Important for VR

                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i); // Get the current eye index

                // Create a copy of the UV coordinates to modify
                float2 stereoUV = i.uv;

                // unity_StereoEyeIndex is 0 for the left eye, 1 for the right eye
                if (unity_StereoEyeIndex == 0) // Left Eye
                {
                    // Map the U coordinate to the left half of the texture (0.0 to 0.5)
                    stereoUV.x = stereoUV.x * 0.5;
                }
                else // Right Eye
                {
                    // Map the U coordinate to the right half of the texture (0.5 to 1.0)
                    stereoUV.x = (stereoUV.x * 0.5) + 0.5;
                }

                // Sample the texture with our modified coordinates
                fixed4 col = tex2D(_MainTex, stereoUV);
                return col;
            }
            ENDCG
        }
    }
}