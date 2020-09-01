using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System.IO;
using System.Diagnostics;

public class GetPose : MonoBehaviour
{


    public GameObject cube;

    Process process;

    Vector3 rotationVector;
    
    //private StreamReader streamReader;

    // Start is called before the first frame update
    void Start()
    {
        ////---------- Process Setting ---------------------------------------------------------------------------------------------------------
        //process = new Process();
        //process.StartInfo.FileName = "cmd.exe";
        //process.StartInfo.UseShellExecute = false;
        //process.StartInfo.CreateNoWindow = true;
        //process.StartInfo.RedirectStandardOutput = true;                                                                    //データをリダイレクトで受け取るためのコマンド
        //process.StartInfo.RedirectStandardError = true;                                                                   //エラー確認用コマンド
        //process.StartInfo.Arguments = "/c " + "activate ml && python " + Application.dataPath + "/Scripts/GetFromCommand.py";
        //process.OutputDataReceived += new DataReceivedEventHandler(p_OutputDataReceived);                                   //データを受け取ったら実行
        //process.ErrorDataReceived += new DataReceivedEventHandler(p_ErrorDataReceived);                                   //エラーを受け取ったら行う


        ////--------- Process Start ------------------------------------------------------------------------------------------------------------
        //process.Start();
        //process.BeginOutputReadLine();                  //リアルタイムで出力を受け取るための設定
        //process.BeginErrorReadLine();                 //リアルタイムでエラー出力を受け取るための設定
        ////UnityEngine.Debug.Log(Application.dataPath);

    }

    // Update is called once per frame
    void Update()
    {
        using (StreamReader sr = File.OpenText("angle_data.txt"))
        {
            string line;
            line = sr.ReadToEnd();
            UnityEngine.Debug.Log(line);
            if (line.Contains(","))
            {
                string[] pose = line.Split(',');
                float[] joint = new float[pose.Length];
                for (int i = 0; i < pose.Length; i++)
                {
                    joint[i] = float.Parse(pose[i]);
                }
                rotationVector = new Vector3(joint[0], joint[1], joint[2]);

                //UnityEngine.Debug.Log("[rotation Vector]" + rotationVector);
                //UnityEngine.Debug.Log(rotationVector);
            }
            
        }
        changeAngle(rotationVector);

    }


    private void OnApplicationQuit()
    {
        //process.Close();
    }

    //void p_OutputDataReceived(object sender, DataReceivedEventArgs e)
    //{
    //    UnityEngine.Debug.Log("[Debug] " + e.Data);
    //    string str = e.Data.ToString();
    //    if (str != null)
    //    {
    //        //UnityEngine.Debug.Log(str);
    //        if (str.Contains(","))
    //        {
    //            string[] pose = str.Split(',');
    //            float[] joint = new float[pose.Length];
    //            for (int i = 0; i < pose.Length; i++)
    //            {
    //                joint[i] = float.Parse(pose[i]);
    //            }
    //            rotationVector = new Vector3(joint[0], joint[1], joint[2]);
    //            //UnityEngine.Debug.Log("[rotation Vector]" + rotationVector);
    //            UnityEngine.Debug.Log("Done!");
    //        }
    //    }
    //}

    void p_ErrorDataReceived(object sender, DataReceivedEventArgs e)
    {
        UnityEngine.Debug.Log("[Error] " + e.Data);
    }

    void changeAngle(Vector3 rotation)
    {
        cube.transform.rotation = Quaternion.Euler(rotation);
    }
}
