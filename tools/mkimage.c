/* From the ATEN SDK, https://www.supermicro.com/wftp/GPL/SMT/IPMI_ATEN_STD_SDK_2.0_11242010.tar.gz
 * SDK/MKIMG_Tool/Host/HERMON/mkimage.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SIGNATURE_WORD   0xA0FFFF9F
unsigned long ulFlashBlockSize = 0x10000;
typedef struct t_footer
{
  unsigned int  num;
  unsigned int  base;
  unsigned int  length;
  unsigned int  load_address;
  unsigned int  exec_address;
  unsigned char name[16];
  unsigned int  image_checksum;
  unsigned int  signature;
  unsigned int  type;
  unsigned int  checksum;
} tfooter;



unsigned int SetImageChecksum(unsigned char *databuf, unsigned int length,unsigned char b_align)
{
	unsigned long long sum;
	unsigned int k, checksum, *data_tmp, data_tail;
	
	data_tail = length & 0x3;
	if(data_tail && b_align)
	{
		for (k = 1; k <= (4 - data_tail); k ++)
		{
			*(databuf + length + k -1) = 0xFF;
		} 
		length = (length&(~0x3)) + 4;	
	}
	
	data_tmp = (unsigned int *) malloc(length + 24);
	memcpy(((unsigned char *)data_tmp), (unsigned char *)(databuf), length);
		
	sum = 0;
	for(k = 0; k < (length/4); k ++)
		sum += *((unsigned int *)data_tmp + k);
	sum = ~((sum&(-1LU))+(sum>>32));	
	
	free(data_tmp);
	return sum;
}


int WriteImage(FILE *fout,tfooter *image_footer, unsigned char  *image_source,unsigned int  length)
{
    int blockSize,dest;
    unsigned char  block_num;
    int k,size,offset;
    int total_len;
    char pattern =0xff;
    int written_size=0;
    
    
    total_len = length;
    offset = 0;
    blockSize = ulFlashBlockSize;
    
    while (length > 0 )
    {
		if ( length >= ulFlashBlockSize)
		    size = ulFlashBlockSize;
		else 
		    size = length;
    	
		fseek(fout,offset,SEEK_SET);
		fwrite( image_source,1,size,fout);
		
		if( length  <= blockSize )
		{
			block_num = (image_footer->length)/blockSize ;
			dest = (block_num * blockSize);
			

			if( ((blockSize - length) < (sizeof(tfooter)) ) && ((image_footer->length)%blockSize != 0) ) 
			{
			    written_size = dest+2*blockSize-sizeof(tfooter);
			}
			else
			{	    
			    written_size = dest+blockSize-sizeof(tfooter);
			}
			if ( total_len < written_size )
			{
			    fseek(fout,total_len,SEEK_SET);
			    for  ( k= 0;k < (written_size - total_len);k++)
				fwrite(&pattern,1,1,fout);
    	
			}
			else 
			{
			    printf ("length error \n");
			}	    
			fseek (fout,written_size ,SEEK_SET);
			fwrite((unsigned char *)image_footer,1, sizeof(tfooter),fout);
		}	
		
		offset += size;
		length -= size;
		image_source += size;
    }
    return 0;
}

void usage ()
{
	fprintf (stderr, "Usage: "
			 "./mkimage -b base_addr -u num -l load_addr -e exec_addr"
			 "-n name -i data_file[:data_file...] -o image -acxfzr\n");
	fprintf (stderr, "          -b	     ==> set flash base address to 'base addr'\n"
			 "          -e	     ==> set execute address to 'exec addr'\n"
			 "          -l	     ==> set load address to 'load addr'\n"
			 "          -acxfzr  ==> set image type to 'type'\n"
			 "          -n       ==> set image name to 'name'\n"
			 "          -u       ==> set image number to 'number'\n"
			 "          -i       ==> use image data from 'datafile'\n"
			 "          -o       ==> use image data to   'data file'\n"
		);
	exit (1);
}

int main(int argc,char *argv[])
{

    FILE *fin,*fout;
    unsigned char buff[64];
    unsigned int length=0,nbytes=0;
    unsigned char *data_ptr,*data_ptr1;
    tfooter image_footer;
    unsigned int checksum;
    int size,offset=0;
    int opt,i;
    unsigned char flag = 0 ;
    unsigned long exec,addr,base_addr;
    char infile[32],outfile[32],name[16];
    int num,modify_length,size_remain;

    while ((opt = getopt (argc,argv,"s:b:e:l:n:i:o:u:acxfzr")) != -1)
    {
	switch (opt)
	{
	    case 'a':
		flag |= 0x01;
		break;
	    case 'c':
		flag |= 0x02;
		break;
	    case 'x':
		flag |= 0x04;
		break;
	    case 'f':
		flag |= 0x08;
		break;
	    case 'z':
		flag |= 0x10;
		break;
	    case 'r':
		flag |= 0x20;
		break;
	    case 'b': 
		base_addr =  strtoul (optarg,NULL,16); 
		break;
		case 's': 
		ulFlashBlockSize =  strtoul (optarg,NULL,16); 
		break;
	    case 'l': 
		addr =  strtoul (optarg,NULL,16); 
		break;
	    case 'e':
		exec = strtoul (optarg,NULL,16);
		break;
	    case 'n':
		strcpy (name,optarg);
		break;
	    case 'i':
		memcpy (infile,optarg,32);
		break;
	    case 'o':
		memcpy (outfile,optarg,32);
		break;
	    case 'u':
		num=atoi(optarg);
		break;
	    default:
	    printf("optarg = 0x%x\n",optarg);
		usage ();
		break;

	}
    }

    fin = fopen (infile,"r");

    if (fin == NULL)
    {
	printf ("Can't find this file!\n");
	exit(1);
    }

    fout = fopen (outfile,"w");

    if (fout == NULL )
    {
	printf ("Can't write the file!\n");
	exit(1);
    }
    while ( !feof(fin) )
    {
	nbytes = fread(buff,1,32,fin);
	length += nbytes;
    }


    data_ptr =  malloc (length +ulFlashBlockSize+ sizeof (tfooter));

    if (data_ptr == NULL )
    {
	printf ("can't alloc MM!\n");
	exit (1);
    }
    memset ( data_ptr,0,length +ulFlashBlockSize+ sizeof (tfooter));

    data_ptr1 = data_ptr;

    rewind(fin);
    while (!feof(fin))
    {
	nbytes = fread(buff,1,32,fin);
	memcpy (data_ptr1,buff,nbytes);
	data_ptr1 += nbytes;
    }

    if(length & 0x3)
		modify_length = (length & (~0x3)) + 4;	
	else
		modify_length = length;



	
	size_remain = ulFlashBlockSize - (modify_length % ulFlashBlockSize) - sizeof(tfooter);
	if((size_remain < 25) && (size_remain >= 0))
		modify_length += 25;

    image_footer.num    = num;
    image_footer.base    =base_addr;
    image_footer.type    = flag;
    image_footer.length    = modify_length;
    image_footer.image_checksum  = SetImageChecksum (data_ptr,modify_length,1);
    image_footer.signature = SIGNATURE_WORD;
    image_footer.load_address = addr;
    image_footer.exec_address = exec;
    strcpy (image_footer.name,name);
    image_footer.checksum  = SetImageChecksum ((unsigned char * )&image_footer,sizeof(tfooter)-4,0);
    
    printf ("\tImage footer information\n");
    printf ("\timage name	   \t:%s\n",name);
    printf ("\timage type	   \t:%x\n",flag);
    printf ("\timage base addrress \t:%x\n",base_addr);
    printf ("\timage exec addrress \t:%x\n",exec);
    printf ("\timage load addrress \t:%x\n",addr);
    printf ("\timage num	   \t:%x\n",num);
    printf ("\timage length	   \t:%x\n",modify_length);
    printf ("\timage image_checksum\t:%x\n",image_footer.image_checksum);
    printf ("\timage checksum	   \t:%x\n",image_footer.checksum);

    WriteImage(fout,&image_footer,data_ptr,modify_length);

    fclose (fin);
    fclose (fout);

    return 0;
}




