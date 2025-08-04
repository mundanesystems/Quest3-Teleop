using UnityEngine;

/// <summary>
/// Manual Oculus Link Setup - Simple and reliable
/// Just add the components you need manually
/// </summary>
public class ManualOculusLinkSetup : MonoBehaviour
{
    [Header("Instructions")]
    [TextArea(5, 10)]
    public string instructions = 
        "MANUAL SETUP STEPS:\n" +
        "1. Create empty GameObject\n" +
        "2. Add 'OculusLinkVideoReceiver' component\n" +
        "3. Create another empty GameObject\n" +
        "4. Add 'OculusLinkGyroscopeReader' component\n" +
        "5. Set IP addresses to 127.0.0.1\n" +
        "6. Connect Quest 3 via USB + enable Oculus Link\n" +
        "7. Start Python servers\n" +
        "8. Hit Play in Unity Editor!";

    [Header("Quick Actions")]
    [Space(10)]
    public bool showDebugInfo = true;

    void Start()
    {
        if (showDebugInfo)
        {
            Debug.Log("=== MANUAL OCULUS LINK SETUP ===");
            Debug.Log(instructions);
            Debug.Log("This approach avoids any script compilation issues!");
        }
    }

    [ContextMenu("Print Setup Instructions")]
    public void PrintInstructions()
    {
        Debug.Log("=== OCULUS LINK SETUP INSTRUCTIONS ===");
        Debug.Log("1. Right-click in Hierarchy > Create Empty");
        Debug.Log("2. Name it 'Video Receiver'");
        Debug.Log("3. Add Component > OculusLinkVideoReceiver");
        Debug.Log("4. Set Server Address to: 127.0.0.1");
        Debug.Log("5. Set Server Port to: 8080");
        Debug.Log("");
        Debug.Log("6. Right-click in Hierarchy > Create Empty");
        Debug.Log("7. Name it 'Gyroscope Reader'");
        Debug.Log("8. Add Component > OculusLinkGyroscopeReader");
        Debug.Log("9. Set PC IP Address to: 127.0.0.1");
        Debug.Log("10. Set Port to: 9050");
        Debug.Log("");
        Debug.Log("11. Connect Quest 3 via USB cable");
        Debug.Log("12. Enable Oculus Link in Quest 3 headset");
        Debug.Log("13. Start your Python servers");
        Debug.Log("14. Hit Play in Unity Editor!");
        Debug.Log("");
        Debug.Log("✓ No more Android builds needed!");
    }

    [ContextMenu("Check Components Available")]
    public void CheckComponents()
    {
        Debug.Log("=== CHECKING AVAILABLE COMPONENTS ===");
        
        bool videoReceiverExists = System.Type.GetType("OculusLinkVideoReceiver") != null;
        bool gyroReaderExists = System.Type.GetType("OculusLinkGyroscopeReader") != null;
        
        Debug.Log($"OculusLinkVideoReceiver: {(videoReceiverExists ? "✓ Available" : "✗ Not found")}");
        Debug.Log($"OculusLinkGyroscopeReader: {(gyroReaderExists ? "✓ Available" : "✗ Not found")}");
        
        if (!videoReceiverExists || !gyroReaderExists)
        {
            Debug.LogWarning("Some components are missing. Check the Console for compile errors.");
            Debug.LogWarning("Make sure all scripts are in the Assets folder and Unity has finished compiling.");
        }
        else
        {
            Debug.Log("✓ All components available! You can add them manually now.");
        }
    }
}
