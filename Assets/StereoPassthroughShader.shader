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
            // make fog work
            #pragma multi_compile_fog

            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float2 uv : TEXCOORD0;
                UNITY_FOG_COORDS(1)
                float4 vertex : SV_POSITION;
            };

            sampler2D _MainTex;
            float4 _MainTex_ST;

            v2f vert (appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                // This is the key part for stereoscopic rendering.
                // unity_StereoEyeIndex is 0 for the left eye, 1 for the right eye.
                
                // Scale UV's x-coordinate by 0.5 to use only half the texture
                float2 stereoUV = i.uv;
                stereoUV.x = stereoUV.x * 0.5;

                // If rendering for the right eye (index 1), shift the x-coordinate
                // to sample from the right half of the texture.
                if (unity_StereoEyeIndex == 1)
                {
                    stereoUV.x += 0.5;
                }

                fixed4 col = tex2D(_MainTex, stereoUV);
                return col;
            }
            ENDCG
        }
    }
}